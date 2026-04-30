"""High-level async client for the CatGenie API."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Literal

from curl_cffi.requests import AsyncSession, Response

from .auth import CatGenieAuth, Credentials
from .const import (
    BASE_URL,
    DEFAULT_HEADERS,
    ENDPOINT_DEVICE_OPERATION,
    ENDPOINT_DEVICE_STATUS,
    ENDPOINT_DEVICES,
    ENDPOINT_FIRMWARE_COMMENTS,
    ENDPOINT_FIRMWARE_UPDATE,
    ENDPOINT_MAINBOARD,
    ENDPOINT_NOTIFICATIONS,
    ENDPOINT_NOTIFICATION_SETTINGS,
    ENDPOINT_PET_STATS,
    ENDPOINT_PETS,
    ENDPOINT_USER,
    TLS_IMPERSONATE,
)
from .models import Device, NotificationList
from .signing import generate_request_headers

_HttpMethod = Literal[
    "GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"
]


class CatGenieClient:
    """Async client for CatGenie device management.

    Usage:
        async with CatGenieClient(credentials) as client:
            devices = await client.get_devices()
    """

    def __init__(
        self,
        credentials: Credentials,
        session: AsyncSession[Response] | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        """Initialise the API client."""
        self._session: AsyncSession[Response] | None = session
        self._owns_session = session is None
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._auth: CatGenieAuth | None = None

    async def __aenter__(self) -> CatGenieClient:
        """Enter the async context manager, creating a session if needed."""
        if self._session is None:
            self._session = AsyncSession(impersonate=TLS_IMPERSONATE)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager, closing the session if owned."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def set_auth(self, auth: CatGenieAuth) -> None:
        """Attach an auth instance for automatic token refresh."""
        self._auth = auth

    async def _ensure_token(self) -> None:
        if self._credentials.is_token_expired and self._auth:
            await self._auth.refresh()

    def _build_headers(
        self,
        path: str,
        method: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers.update(
            generate_request_headers(
                path=path,
                method=method,
                body=body,
                params=params,
                secret=self._credentials.secret,
            )
        )
        if self._credentials.access_token:
            headers["authorization"] = f"Bearer {self._credentials.access_token}"
        return headers

    async def _request(
        self,
        method: _HttpMethod,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if self._session is None:
            raise RuntimeError(
                "CatGenieClient must be used as an async context manager"
            )
        await self._ensure_token()
        url = f"{self._base_url}/{path.lstrip('/')}"
        data = (
            json.dumps(body, separators=(",", ":")).encode()
            if method.upper() in ("POST", "PUT", "PATCH") and body is not None
            else None
        )
        headers = self._build_headers(path, method, body, params)
        resp = await self._session.request(
            method,
            url,
            headers=headers,
            data=data,
            params=params,
            impersonate=TLS_IMPERSONATE,
            default_headers=False,
        )
        if resp.status_code == 401 and self._auth:
            await self._auth.refresh()
            headers = self._build_headers(path, method, body, params)
            resp = await self._session.request(
                method,
                url,
                headers=headers,
                data=data,
                params=params,
                impersonate=TLS_IMPERSONATE,
                default_headers=False,
            )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    # ── Devices ──────────────────────────────────────────────────────

    async def get_devices(self) -> list[Device]:
        """Get all devices associated with the account."""
        data = await self._request(
            "GET",
            ENDPOINT_DEVICES,
            params={"useFleetIndexAndGetRealConnectivity": "true"},
        )
        return [Device.model_validate(d) for d in data.get("thingList", [])]

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get the current status shadow for a device."""
        path = ENDPOINT_DEVICE_STATUS.format(device_id=device_id)
        return await self._request("GET", path)

    async def start_cleaning(self, device_id: str) -> dict[str, Any]:
        """Start a manual cleaning cycle on the given device."""
        path = ENDPOINT_DEVICE_OPERATION.format(device_id=device_id)
        return await self._request("POST", path, body={"state": 1})

    async def stop_cleaning(self, device_id: str) -> dict[str, Any]:
        """Stop an active cleaning cycle on the given device."""
        path = ENDPOINT_DEVICE_OPERATION.format(device_id=device_id)
        return await self._request("POST", path, body={"state": 0})

    # ── Account / Pets ───────────────────────────────────────────────

    async def get_account(self) -> dict[str, Any]:
        """Get current user profile (id, email, accountId, etc.)."""
        return await self._request("GET", ENDPOINT_USER)

    async def get_pets(self) -> list[dict[str, Any]]:
        """Get all pets associated with the account."""
        return await self._request("GET", ENDPOINT_PETS)

    async def get_pet_statistics(self) -> dict[str, Any]:
        """Get usage statistics aggregated per pet."""
        return await self._request("GET", ENDPOINT_PET_STATS)

    # ── Notifications ────────────────────────────────────────────────

    async def get_notifications(self) -> NotificationList:
        """Get the notification history for the account."""
        data = await self._request("GET", ENDPOINT_NOTIFICATIONS)
        return NotificationList.model_validate(data)

    async def get_notification_settings(self) -> dict[str, Any]:
        """Get push notification preferences for the account."""
        return await self._request("GET", ENDPOINT_NOTIFICATION_SETTINGS)

    # ── Firmware ─────────────────────────────────────────────────────

    async def get_firmware_info(self, manufacturer_id: str) -> dict[str, Any]:
        """Get available firmware update info for a device."""
        path = ENDPOINT_FIRMWARE_UPDATE.format(manufacturer_id=manufacturer_id)
        return await self._request("GET", path)

    async def get_firmware_comments(self, version: str) -> dict[str, Any]:
        """Get release notes for a specific firmware version."""
        return await self._request(
            "GET", ENDPOINT_FIRMWARE_COMMENTS, params={"name": version}
        )

    async def get_mainboard(self, manufacturer_id: str) -> dict[str, Any]:
        """Get mainboard hardware details for a device."""
        path = ENDPOINT_MAINBOARD.format(manufacturer_id=manufacturer_id)
        return await self._request("GET", path)
