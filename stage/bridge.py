"""Local stdio→remote-HTTP MCP bridge.

Why this exists: the knowledge MCP runs as a streamable-HTTP service at
`knowledge-mcp.moose-{dev,stg}.armis.com/mcp` and authenticates each
request with a short-lived JWT. Claude Code's `type: http` MCP transport
can only inject static headers from the .mcp.json manifest, so users had
to keep a long-lived `ARMIS_KNOWLEDGE_TOKEN_*` env var refreshed by hand
(or by a session-start hook racing with launchctl).

This bridge runs locally as a stdio MCP server, exchanges
`ARMIS_CLIENT_ID` + `ARMIS_CLIENT_SECRET` for a JWT on first use (and
refreshes <5 min from expiry), and forwards every MCP JSON-RPC message
bidirectionally to the remote endpoint with a fresh bearer token
attached. Tenant routing is resolved server-side from the
`admin.client_credentials` table — the bridge no longer needs a
tenant identifier in env. Same auth lifecycle as armis-appsec-mcp.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

import anyio
import httpx
from dotenv import load_dotenv
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage

from auth import JWTAuth

# Load $CLAUDE_PLUGIN_ROOT/.env (or, when unset, the bridge's own dir) before
# resolving config. override=False means real shell env always wins — same
# precedence as the shell-skills variant.
_plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).parent)
_env_file = _plugin_root / ".env"
if _env_file.is_file():
    load_dotenv(_env_file, override=False)

logger = logging.getLogger("knowledge-mcp-bridge")


_DEFAULT_API_URL = "https://knowledge-api.moose-stg.armis.com"
_DEFAULT_MCP_URL = "https://knowledge-mcp.moose-stg.armis.com/mcp/"


class BearerAuth(httpx.Auth):
    """httpx auth flow that pulls a fresh JWT from JWTAuth on each request.

    On 401, invalidates the cached token and retries once. This handles the
    edge case where the server rotated keys between our exchange and a
    subsequent request — without it, we'd 401-loop until the in-memory
    token's local expiry passed.
    """

    requires_response_body = False

    def __init__(self, jwt_auth: JWTAuth) -> None:
        self._jwt_auth = jwt_auth

    def auth_flow(self, request):  # type: ignore[override]
        request.headers["Authorization"] = self._jwt_auth.get_header()
        response = yield request
        if response.status_code == 401:
            self._jwt_auth.invalidate()
            request.headers["Authorization"] = self._jwt_auth.get_header()
            yield request


def _resolve_config() -> tuple[str, str, str]:
    """Read configuration from env.

    Returns (api_url, mcp_url, client_id). Missing required env vars raise
    RuntimeError with an actionable message rather than crashing later
    inside an async task group.

    Credential precedence: ARMIS_KNOWLEDGE_CLIENT_{ID,SECRET} (knowledge-
    specific override) > ARMIS_CLIENT_{ID,SECRET} (shared default also used
    by armis-appsec). Only the shared names are documented; the prefixed
    names exist so users with different credentials per service can override
    without colliding.
    """
    api_url = os.environ.get("ARMIS_KNOWLEDGE_API_URL") or _DEFAULT_API_URL
    mcp_url = os.environ.get("ARMIS_KNOWLEDGE_MCP_URL") or _DEFAULT_MCP_URL

    client_id = (
        os.environ.get("ARMIS_KNOWLEDGE_CLIENT_ID")
        or os.environ.get("ARMIS_CLIENT_ID")
        or ""
    )
    client_secret = (
        os.environ.get("ARMIS_KNOWLEDGE_CLIENT_SECRET")
        or os.environ.get("ARMIS_CLIENT_SECRET")
        or ""
    )
    if not client_id:
        raise RuntimeError("ARMIS_CLIENT_ID is not set in environment.")
    if not client_secret:
        raise RuntimeError("ARMIS_CLIENT_SECRET is not set in environment.")

    return api_url, mcp_url, client_id


async def _pump(
    src: object,  # MemoryObjectReceiveStream[SessionMessage | Exception]
    dst: object,  # MemoryObjectSendStream[SessionMessage]
    direction: str,
) -> None:
    """Forward messages from `src` to `dst` until either side closes.

    `src` may yield Exception values when the upstream JSON-RPC parse
    fails; we log and drop those rather than crashing the bridge — the
    upstream library has already isolated the failure to a single message.
    """
    try:
        async for item in cast(AsyncGenerator[object, None], src):
            if isinstance(item, Exception):
                logger.warning("%s: dropped malformed message: %r", direction, item)
                continue
            await cast(object, dst).send(item)  # type: ignore[attr-defined]
    except anyio.EndOfStream:
        pass


def _find_leaf(exc: BaseException, *types: type[BaseException]) -> BaseException | None:
    """Walk an ExceptionGroup tree for the first leaf of any of `types`.

    streamablehttp_client raises errors wrapped in nested anyio task-group
    ExceptionGroups; surfacing the original cause makes the difference
    between "MCP server connection timed out after 30000ms" and a one-line
    "421 Invalid Host header" in the user's terminal.
    """
    if isinstance(exc, types):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            found = _find_leaf(sub, *types)
            if found is not None:
                return found
    return None


async def _run_bridge() -> None:
    api_url, mcp_url, client_id = _resolve_config()

    jwt_auth = JWTAuth(
        api_url=api_url,
        client_id=client_id,
    )
    # Force the first exchange now so credential errors surface at startup
    # (visible in stderr / Claude Code's MCP server log) rather than on the
    # first tool call as a confusing JSON-RPC error.
    jwt_auth.exchange()

    bearer = BearerAuth(jwt_auth)

    async with stdio_server() as (client_read, client_write):
        async with streamablehttp_client(mcp_url, auth=bearer) as (
            upstream_read,
            upstream_write,
            _get_session_id,
        ):
            async with anyio.create_task_group() as tg:
                tg.start_soon(_pump, client_read, upstream_write, "client→upstream")
                tg.start_soon(_pump, upstream_read, client_write, "upstream→client")


def _configure_logging() -> None:
    """Wire stderr (always) + an optional file handler.

    KNOWLEDGE_MCP_BRIDGE_LOG, if set, names a path to also tee log lines
    to. Useful when Claude Code is launching the bridge and the user
    can't see stderr — pair with `LOG_LEVEL=DEBUG` to capture the JWT
    exchange URL, response status, exp, and 401-retry hits.

    Failures opening the log file are non-fatal: print one warning to
    stderr and continue with stderr-only logging. We never want a typo'd
    log path to take the bridge down.
    """
    level = os.environ.get("LOG_LEVEL", "INFO")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # stdout is the MCP wire — never log there.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)

    handlers: list[logging.Handler] = [stderr_handler]

    log_path = os.environ.get("KNOWLEDGE_MCP_BRIDGE_LOG")
    if log_path:
        try:
            file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as e:
            print(
                f"warning: could not open KNOWLEDGE_MCP_BRIDGE_LOG={log_path!r}: {e}",
                file=sys.stderr,
            )

    logging.basicConfig(level=level, handlers=handlers, force=True)
    if log_path and len(handlers) > 1:
        logger.info("file logging enabled at %s (level=%s)", log_path, level)


def _diagnose() -> int:
    """Self-test: exercise env, /auth/token, and /mcp/ then print a verdict.

    Returns 0 if everything's wired correctly, 1 otherwise. Output is
    intended for an interactive terminal — it's safe to print to stdout
    here because the caller passed --diagnose and is not speaking
    JSON-RPC over the pipe.
    """
    out = sys.stdout

    def _say(label: str, status: str, detail: str = "") -> None:
        sigil = {"ok": "[ ok ]", "warn": "[warn]", "fail": "[fail]"}.get(status, "[ ?? ]")
        line = f"{sigil} {label}"
        if detail:
            line += f" — {detail}"
        print(line, file=out)

    # --- step 1: env vars ---
    api_url_env = os.environ.get("ARMIS_KNOWLEDGE_API_URL")
    mcp_url_env = os.environ.get("ARMIS_KNOWLEDGE_MCP_URL")
    cid_env = (
        os.environ.get("ARMIS_KNOWLEDGE_CLIENT_ID")
        or os.environ.get("ARMIS_CLIENT_ID")
    )
    sec_env = (
        os.environ.get("ARMIS_KNOWLEDGE_CLIENT_SECRET")
        or os.environ.get("ARMIS_CLIENT_SECRET")
    )

    print(f"plugin root:    {_plugin_root}", file=out)
    print(f".env file:      {_env_file} ({'present' if _env_file.is_file() else 'absent'})", file=out)
    print(f"api url:        {api_url_env or _DEFAULT_API_URL}", file=out)
    print(f"mcp url:        {mcp_url_env or _DEFAULT_MCP_URL}", file=out)
    print(f"client id:      {cid_env or '(missing)'}", file=out)
    print(f"client secret:  {'set (' + str(len(sec_env)) + ' chars)' if sec_env else '(missing)'}", file=out)
    print("", file=out)

    if not cid_env or not sec_env:
        _say("env", "fail", "ARMIS_CLIENT_ID and ARMIS_CLIENT_SECRET must both be set")
        return 1
    _say("env", "ok")

    # --- step 2: token exchange ---
    try:
        api_url, mcp_url, client_id = _resolve_config()
    except RuntimeError as e:
        _say("config", "fail", str(e))
        return 1

    jwt_auth = JWTAuth(api_url=api_url, client_id=client_id)
    try:
        jwt_auth.exchange()
    except RuntimeError as e:
        _say("token exchange", "fail", str(e))
        return 1

    token = jwt_auth.get_token()
    claims = _decode_jwt_payload_unverified(token)
    exp_in = claims.get("exp", 0) - int(__import__("time").time())
    claim_summary = ", ".join(
        f"{k}={claims[k]}" for k in ("sub", "tenant", "kind", "role") if k in claims
    )
    _say(
        "token exchange",
        "ok",
        f"alg={_jwt_alg(token)}, exp in {exp_in}s, claims: {claim_summary or '(none)'}",
    )

    # --- step 3: /mcp/ round-trip ---
    headers = {
        "authorization": f"Bearer {token}",
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "knowledge-mcp-diagnose", "version": "1.0"},
        },
    }
    try:
        resp = httpx.post(mcp_url, headers=headers, json=initialize_payload, timeout=15.0)
    except httpx.HTTPError as e:
        _say("mcp connect", "fail", f"{type(e).__name__}: {e}")
        return 1

    if resp.status_code == 401:
        _say(
            "mcp /mcp/",
            "fail",
            "401 — the MCP rejected our token. Check JWT_PUBLIC_KEY/aud/iss on the MCP service.",
        )
        return 1
    if resp.status_code >= 400:
        body = resp.text.strip()[:200]
        _say("mcp /mcp/", "fail", f"HTTP {resp.status_code}: {body or '<empty body>'}")
        return 1

    _say(
        "mcp /mcp/",
        "ok",
        f"HTTP {resp.status_code}, session={resp.headers.get('mcp-session-id', '(none)')}",
    )
    print("", file=out)
    print("All checks passed. Bridge auth is healthy.", file=out)
    return 0


def _decode_jwt_payload_unverified(token: str) -> dict:
    """Decode the payload of a JWT without verifying — diagnostics only."""
    import base64
    import json as _json

    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return _json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, _json.JSONDecodeError):
        return {}


def _jwt_alg(token: str) -> str:
    import base64
    import json as _json

    parts = token.split(".")
    if len(parts) != 3:
        return "?"
    header_b64 = parts[0] + "=" * (-len(parts[0]) % 4)
    try:
        header = _json.loads(base64.urlsafe_b64decode(header_b64))
        return header.get("alg", "?")
    except (ValueError, _json.JSONDecodeError):
        return "?"


def main() -> None:
    _configure_logging()
    if "--diagnose" in sys.argv[1:]:
        sys.exit(_diagnose())
    try:
        anyio.run(_run_bridge)
    except RuntimeError as e:
        # Configuration / auth errors: print one line to stderr and exit
        # nonzero so Claude Code surfaces the failure cleanly.
        logger.error("%s", e)
        sys.exit(1)
    except BaseExceptionGroup as eg:
        # streamablehttp_client wraps upstream HTTP failures in nested
        # ExceptionGroups. Without unwrapping, Claude Code only sees a 30s
        # connect timeout — the actual cause (e.g. "421 Invalid Host
        # header" from MCP's TransportSecurityMiddleware) gets lost.
        status_err = _find_leaf(eg, httpx.HTTPStatusError)
        if isinstance(status_err, httpx.HTTPStatusError):
            # The streamable-HTTP client raises with the response body still
            # un-consumed, so .text/.content would raise ResponseNotRead.
            # Read it lazily and best-effort — the status line is the
            # actionable signal even if the body never decodes.
            body = ""
            try:
                body = (status_err.response.read().decode("utf-8", "replace")).strip()[:200]
            except Exception:  # noqa: BLE001
                pass
            logger.error(
                "upstream MCP returned HTTP %d %s for %s: %s",
                status_err.response.status_code,
                status_err.response.reason_phrase,
                status_err.request.url,
                body or "<empty body>",
            )
            sys.exit(1)
        transport_err = _find_leaf(
            eg, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout
        )
        if transport_err is not None:
            logger.error("upstream MCP connect failed: %s", transport_err)
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()


# Silence unused-import warning: SessionMessage is referenced only via type
# annotations in the docstring. Importing it ensures any downstream type
# changes break this file at install time, not later at runtime.
_ = SessionMessage
