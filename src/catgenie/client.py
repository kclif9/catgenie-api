"""High-level async client for the CatGenie API."""

from __future__ import annotations

import json
from typing import Any, Literal

from curl_cffi.requests import AsyncSession, Response

from .auth import CatGenieAuth, Credentials
from .const import (
    BASE_URL,
    DEFAULT_HEADERS,
    ENDPOINT_DEVICE_CONFIG,
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
from .exceptions import CatGenieAPIError
from .models import CleaningMode, Device, NotificationList, ScheduleEntry
from .signing import generate_request_headers

_HttpMethod = Literal[
    "GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"
]


class CatGenieClient:
    """Async client for CatGenie device management.

    Usage::

        client = CatGenieClient(credentials)
        devices = await client.get_devices()

        # On teardown:
        await client.async_close()
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

    async def async_close(self) -> None:
        """Close the underlying HTTP session if it was created by this instance."""
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
            self._session = AsyncSession(impersonate=TLS_IMPERSONATE)
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
        if resp.status_code < 200 or resp.status_code >= 300:
            raise CatGenieAPIError(
                f"API request failed: {method} {path} " f"(status={resp.status_code})"
            )
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

    # ── Configuration ────────────────────────────────────────────────

    async def update_configuration(
        self, device_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Update device configuration with partial field(s).

        Args:
            device_id: The device manufacturer ID.
            **kwargs: Configuration fields to update (camelCase API keys).

        Returns:
            API response dict.

        Raises:
            CatGenieAPIError: If the API returns a non-2xx response.
        """
        path = ENDPOINT_DEVICE_CONFIG.format(device_id=device_id)
        return await self._request("PUT", path, body=kwargs)

    async def set_volume(self, device_id: str, level: int) -> dict[str, Any]:
        """Set the device speaker volume level.

        Args:
            device_id: The device manufacturer ID.
            level: Volume level (1–7).

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, volumeLevel=level)

    async def set_child_lock(self, device_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable the child lock.

        Args:
            device_id: The device manufacturer ID.
            enabled: True to enable, False to disable.

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, childLock=int(enabled))

    async def set_auto_lock(self, device_id: str, seconds: int) -> dict[str, Any]:
        """Set the auto-lock timeout in seconds.

        Args:
            device_id: The device manufacturer ID.
            seconds: Timeout in seconds (0 to disable).

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, autoLock=seconds)

    async def set_extra_dry(self, device_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable the extra dry cycle.

        Args:
            device_id: The device manufacturer ID.
            enabled: True to enable, False to disable.

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, extraDry=enabled)

    async def set_cat_delay(self, device_id: str, seconds: int) -> dict[str, Any]:
        """Set the delay after cat detection before starting a cycle.

        Args:
            device_id: The device manufacturer ID.
            seconds: Delay in seconds.

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, catDelay=seconds)

    async def set_cat_sensitivity(self, device_id: str, value: int) -> dict[str, Any]:
        """Set the cat sensor sensitivity.

        Args:
            device_id: The device manufacturer ID.
            value: Sensitivity value.

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, catSense=value)

    async def set_cleaning_mode(
        self, device_id: str, mode: CleaningMode
    ) -> dict[str, Any]:
        """Set the cleaning trigger mode (automatic or manual).

        Args:
            device_id: The device manufacturer ID.
            mode: CleaningMode.AUTOMATIC or CleaningMode.MANUAL.

        Returns:
            API response dict.
        """
        return await self.update_configuration(device_id, mode=int(mode))

    async def set_schedule(
        self, device_id: str, entries: list[ScheduleEntry]
    ) -> dict[str, Any]:
        """Set the cleaning schedule.

        Args:
            device_id: The device manufacturer ID.
            entries: List of ScheduleEntry objects defining the schedule.

        Returns:
            API response dict.
        """
        schedule_data = [
            entry.model_dump(by_alias=True, exclude_none=True) for entry in entries
        ]
        return await self.update_configuration(device_id, schedule=schedule_data)

    async def set_dnd(
        self, device_id: str, from_time: str, to_time: str
    ) -> dict[str, Any]:
        """Set the Do Not Disturb window.

        Args:
            device_id: The device manufacturer ID.
            from_time: Start time in "HH:MM" format.
            to_time: End time in "HH:MM" format.

        Returns:
            API response dict.
        """
        return await self.update_configuration(
            device_id, dndFrom=from_time, dndTo=to_time
        )

    async def set_extra_wash(self, device_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable the 4-wash cycle (extra wash).

        Args:
            device_id: The device manufacturer ID.
            enabled: True to enable, False to disable.

        Returns:
            API response dict.
        """
        return await self.update_configuration(
            device_id, binaryElements={"EXTRA_WASH": enabled}
        )

    async def set_extra_shake(self, device_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable the arm shake cycle.

        Args:
            device_id: The device manufacturer ID.
            enabled: True to enable, False to disable.

        Returns:
            API response dict.
        """
        return await self.update_configuration(
            device_id, binaryElements={"EXTRA_SHAKE": enabled}
        )
