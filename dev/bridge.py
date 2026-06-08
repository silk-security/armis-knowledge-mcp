"""Local stdio→remote-HTTP MCP bridge.

Why this exists: the knowledge MCP runs as a streamable-HTTP service at
`knowledge-mcp.moose-{dev,stg}.armis.com/mcp` and authenticates each
request with a short-lived JWT. Claude Code's `type: http` MCP transport
can only inject static headers from the .mcp.json manifest, so users had
to keep a long-lived `ARMIS_KNOWLEDGE_TOKEN_*` env var refreshed by hand
(or by a session-start hook racing with launchctl).

This bridge runs locally as a stdio MCP server, exchanges
`ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` / `ARMIS_TENANT_SLUG` for a JWT
on first use (and refreshes <5 min from expiry), and forwards every MCP
JSON-RPC message bidirectionally to the remote endpoint with a fresh
bearer token attached. Same auth lifecycle as armis-appsec-mcp.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncGenerator
from typing import cast

import anyio
import httpx
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage

from auth import JWTAuth

logger = logging.getLogger("knowledge-mcp-bridge")


_DEFAULT_API_URL = "https://knowledge-api.moose-dev.armis.com"
_DEFAULT_MCP_URL = "https://knowledge-mcp.moose-dev.armis.com/mcp/"


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


def _resolve_config() -> tuple[str, str, str, str]:
    """Read configuration from env. Returns (api_url, mcp_url, client_id, tenant_slug).

    Missing required env vars raise RuntimeError with an actionable message
    rather than crashing later inside an async task group.
    """
    api_url = os.environ.get("ARMIS_KNOWLEDGE_API_URL") or _DEFAULT_API_URL
    mcp_url = os.environ.get("ARMIS_KNOWLEDGE_MCP_URL") or _DEFAULT_MCP_URL

    client_id = os.environ.get("ARMIS_CLIENT_ID", "")
    if not client_id:
        raise RuntimeError("ARMIS_CLIENT_ID is not set in environment.")
    if not os.environ.get("ARMIS_CLIENT_SECRET"):
        raise RuntimeError("ARMIS_CLIENT_SECRET is not set in environment.")

    tenant_slug = os.environ.get("ARMIS_TENANT_SLUG", "")
    if not tenant_slug:
        raise RuntimeError("ARMIS_TENANT_SLUG is not set in environment.")

    return api_url, mcp_url, client_id, tenant_slug


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
    api_url, mcp_url, client_id, tenant_slug = _resolve_config()

    jwt_auth = JWTAuth(api_url=api_url, client_id=client_id, tenant_slug=tenant_slug)
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


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        # stdout is the MCP wire — log to stderr only.
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
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
