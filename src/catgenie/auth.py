"""Authentication for the CatGenie API.

The CatGenie app uses phone-number + SMS code authentication:
1. POST generateLoginCode/v2  → triggers SMS to the user's phone
2. POST loginByPhoneNumber/v2 → exchanges phone + code for JWT + refresh token

The phone number is sent encrypted in a "str1" field:
  str1 = AES-CBC("+{countryCode}{phone}-{random8chars}", static_key, zero_iv)

generateLoginCode requires only x-pm-en-dec/x-pm-en-ver/x-render-t headers.
loginByPhoneNumber additionally requires y-pm-sg-b/y-pm-sg-p HMAC signatures
*in the captured app traffic*, but the server does NOT validate them — login
succeeds without the signing secret.

The refresh token is very long-lived (~10 years) and can be used to obtain
short-lived access tokens (30-minute expiry) via the refreshToken/v2 endpoint.

CRITICAL: requests must be sent with a mobile/browser TLS fingerprint
(via curl_cffi `impersonate`). Python stdlib SSL is silently filtered at
the edge — server returns 200 OK / empty body but never sends the SMS.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, cast

from curl_cffi.requests import AsyncSession, Response

from .const import (
    BASE_URL,
    DEFAULT_HEADERS,
    ENDPOINT_CONFIG_URL,
    ENDPOINT_GENERATE_LOGIN_CODE,
    ENDPOINT_LOGIN_BY_PHONE,
    ENDPOINT_REFRESH_TOKEN,
    TLS_IMPERSONATE,
)
from .exceptions import CatGenieAuthenticationError, CatGenieAPIError
from .signing import encrypt_str1, generate_request_headers

_HttpMethod = Literal[
    "GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"
]


@dataclass
class Credentials:
    """Stored authentication state."""

    access_token: str = ""
    refresh_token: str = ""
    secret: str = ""  # 84-char HMAC signing secret (optional — server doesn't validate)
    token_expiration: float = 0.0  # Unix timestamp (seconds)
    account_id: str = ""
    user_id: str = ""
    tenant_id: str = ""

    @property
    def is_token_expired(self) -> bool:
        """Return True if the access token is absent or has expired."""
        return not self.access_token or time.time() >= self.token_expiration


class CatGenieAuth:
    """Handles the CatGenie phone-number authentication flow.

    Usage::

        auth = CatGenieAuth()
        await auth.request_login_code(country_code=60, phone="400000000")
        code = input("SMS code: ")
        creds = await auth.login(country_code=60, phone="400000000", code=code)

        # On teardown:
        await auth.async_close()
    """

    def __init__(
        self,
        session: AsyncSession[Response] | None = None,
        base_url: str = BASE_URL,
        secret: str = "",
    ) -> None:
        """Initialise the auth client."""
        self._session: AsyncSession[Response] | None = session
        self._owns_session = session is None
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self.credentials = Credentials(secret=secret)

    async def async_close(self) -> None:
        """Close the underlying HTTP session if it was created by this client."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _build_headers(
        self,
        path: str,
        method: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        require_hmac: bool = True,
    ) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        secret = self.credentials.secret or self._secret if require_hmac else ""
        headers.update(
            generate_request_headers(
                path=path,
                method=method,
                body=body,
                params=params,
                secret=secret,
            )
        )
        return headers

    async def _request(
        self,
        method: _HttpMethod,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        require_hmac: bool = True,
        token: str = "",
    ) -> Any:
        if self._session is None:
            self._session = AsyncSession(impersonate=TLS_IMPERSONATE)
        headers = self._build_headers(path, method, body, params, require_hmac)
        if token:
            headers["authorization"] = f"Bearer {token}"
        data = (
            json.dumps(body, separators=(",", ":")).encode()
            if method.upper() in ("POST", "PUT", "PATCH") and body is not None
            else None
        )
        return await self._session.request(
            method,
            self._url(path),
            headers=headers,
            data=data,
            params=params,
            impersonate=TLS_IMPERSONATE,
            default_headers=False,
        )

    # ── Public API ──────────────────────────────────────────────────

    async def get_base_url(self, country_code: int, phone: str) -> dict[str, Any]:
        """GET config/v1/url — preflight call the app makes before login.

        We mirror this to keep the on-wire flow identical to the real app.
        """
        resp = await self._request(
            "GET",
            ENDPOINT_CONFIG_URL,
            params={"countryCode": f"+{country_code}", "phone": phone},
            require_hmac=False,
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise CatGenieAPIError(
                f"Config URL request failed (status={resp.status_code})"
            )
        return cast(dict[str, Any], resp.json())

    async def request_login_code(self, country_code: int, phone: str) -> dict[str, Any]:
        """POST generateLoginCode/v2 — triggers SMS verification code.

        Body: {"str1": "<AES-encrypted phone>"}

        The server always returns 200 regardless of success or failure.
        A missing SMS typically indicates the str1 payload was rejected
        (the server silently discards malformed requests).

        Returns:
            Dict with ``status`` key (HTTP status code).
        """
        body = {"str1": encrypt_str1(country_code, phone)}
        resp = await self._request(
            "POST",
            ENDPOINT_GENERATE_LOGIN_CODE,
            body=body,
            require_hmac=False,
        )
        return {"status": resp.status_code, "data": {}}

    async def login(
        self,
        country_code: int,
        phone: str,
        code: str,
    ) -> Credentials:
        """POST loginByPhoneNumber/v2 — exchange SMS code for tokens."""
        body = {"str1": encrypt_str1(country_code, phone), "code": code}
        resp = await self._request("POST", ENDPOINT_LOGIN_BY_PHONE, body=body)
        if resp.status_code != 200 or not resp.content:
            raise CatGenieAuthenticationError(
                f"Login failed (status={resp.status_code}, body={resp.content!r}). "
                "SMS code is likely expired or already consumed; request a new one."
            )
        data = resp.json()
        self.credentials = Credentials(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            secret=self._secret,
            token_expiration=_parse_expiration(data.get("expiration", 0)),
            account_id=data.get("accountId", ""),
            user_id=data.get("userId", ""),
            tenant_id=data.get("tenantId", ""),
        )
        return self.credentials

    async def refresh(self) -> Credentials:
        """POST refreshToken/v2 — get a fresh JWT using the refresh token."""
        if not self.credentials.refresh_token:
            raise CatGenieAuthenticationError("No refresh token available")
        body = {"refreshToken": self.credentials.refresh_token}
        resp = await self._request("POST", ENDPOINT_REFRESH_TOKEN, body=body)
        if resp.status_code == 401:
            raise CatGenieAuthenticationError(f"Refresh token rejected: {resp.text}")
        if resp.status_code < 200 or resp.status_code >= 300:
            raise CatGenieAPIError(f"Token refresh failed (status={resp.status_code})")
        data = resp.json()
        self.credentials.access_token = data.get("token", "")
        self.credentials.token_expiration = _parse_expiration(data.get("expiration", 0))
        return self.credentials


def _parse_expiration(value: int | float | str) -> float:
    """Parse expiration — API returns milliseconds since epoch."""
    try:
        ms = int(value)
        return ms / 1000.0 if ms > 1_000_000_000_000 else float(ms)
    except (ValueError, TypeError):
        return 0.0
