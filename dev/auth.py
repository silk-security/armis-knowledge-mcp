"""JWT auth for the local stdio bridge.

Exchanges ARMIS_CLIENT_ID / ARMIS_CLIENT_SECRET / ARMIS_TENANT_SLUG for a
short-lived bearer token via POST /api/v1/auth/token on the knowledge API.
Token is held in memory and refreshed when within 5 min of expiry.

Mirrors the shape of armis-appsec-mcp/auth.py so behavior is consistent
across the two MCPs.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.parse

import httpx

logger = logging.getLogger("knowledge-mcp-bridge")

_REFRESH_BUFFER_SECONDS = 300
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}


class JWTAuth:
    """In-memory JWT manager.

    Not thread-safe. The bridge serializes upstream calls through a single
    HTTP session, so concurrent access is not a concern.
    """

    def __init__(self, api_url: str, client_id: str, tenant_slug: str) -> None:
        self._api_url = api_url
        self._client_id = client_id
        self._tenant_slug = tenant_slug
        self._token: str | None = None
        self._expires_at: float = 0.0

    def exchange(self) -> None:
        url = f"{self._api_url.rstrip('/')}/api/v1/auth/token"

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" and parsed.hostname not in _LOCALHOST_HOSTS:
            raise RuntimeError("ARMIS_KNOWLEDGE_API_URL must use HTTPS (except localhost).")

        # Read secret on each exchange so it isn't pinned in process memory
        # for the lifetime of the bridge. Same pattern as armis-appsec-mcp.
        client_secret = os.environ.get("ARMIS_CLIENT_SECRET", "")
        if not client_secret:
            raise RuntimeError("ARMIS_CLIENT_SECRET is not set in environment.")

        try:
            response = httpx.post(
                url,
                json={
                    "client_id": self._client_id,
                    "client_secret": client_secret,
                    "tenant_slug": self._tenant_slug,
                },
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RuntimeError(
                    "Authentication failed: invalid client_id/client_secret/tenant_slug"
                ) from e
            raise RuntimeError(f"Authentication failed: HTTP {e.response.status_code}") from e
        except httpx.TimeoutException as e:
            raise RuntimeError("Authentication failed: connection timeout") from e
        except Exception as e:
            raise RuntimeError(f"Authentication failed: {e}") from e

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError("Authentication failed: invalid response (expected JSON)") from e

        if "token" not in data:
            raise RuntimeError("Authentication failed: unexpected response (missing token)")

        self._token = data["token"]
        try:
            self._expires_at = self._parse_jwt_exp(self._token)
        except (ValueError, KeyError) as e:
            self._token = None
            raise RuntimeError(f"Authentication failed: invalid JWT payload ({e})") from e
        logger.info("JWT obtained, expires at %.0f", self._expires_at)

    def _is_valid(self) -> bool:
        return self._token is not None and time.time() < self._expires_at - _REFRESH_BUFFER_SECONDS

    def get_token(self) -> str:
        if not self._is_valid():
            self.exchange()
        assert self._token is not None
        return self._token

    def get_header(self) -> str:
        return f"Bearer {self.get_token()}"

    def invalidate(self) -> None:
        """Force a refresh on the next get_token() call.

        Used when the upstream returns 401 with a token we believed valid —
        e.g. server-side rotation or clock skew.
        """
        self._token = None
        self._expires_at = 0.0

    @staticmethod
    def _parse_jwt_exp(token: str) -> float:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 dot-separated parts")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = float(payload["exp"])
        now = time.time()
        if exp <= now:
            raise ValueError("JWT exp is in the past")
        if exp > now + 86400:
            raise ValueError("JWT exp is more than 24h in the future")
        return exp
