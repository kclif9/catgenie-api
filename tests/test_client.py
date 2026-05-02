"""Tests for catgenie.client — CatGenieClient methods."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from catgenie.auth import Credentials
from catgenie.client import CatGenieClient
from catgenie.models import CleaningMode, ScheduleEntry


def _make_credentials() -> Credentials:
    """Create valid non-expired credentials for testing."""
    return Credentials(
        access_token="test.jwt.token",
        refresh_token="test.refresh.token",
        secret="A" * 84,
        token_expiration=time.time() + 3600,
        account_id="acct-123",
        user_id="user-456",
        tenant_id="tenant-789",
    )


def _make_mock_session(json_data: dict | None = None) -> AsyncMock:
    """Create a mock AsyncSession that returns a canned response."""
    mock_session = AsyncMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.content = (
        b'{"ok": true}' if json_data is None else json.dumps(json_data).encode()
    )
    resp.json.return_value = json_data if json_data is not None else {"ok": True}
    mock_session.request.return_value = resp
    return mock_session


class TestUpdateConfiguration:
    """Tests for update_configuration and typed setter methods."""

    @pytest.mark.asyncio
    async def test_update_configuration_sends_post(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.update_configuration("DEV001", volumeLevel=5)

        session.request.assert_called_once()
        call_args = session.request.call_args
        assert call_args[0][0] == "POST"
        assert "DEV001/configuration" in call_args[0][1]
        data = json.loads(call_args[1]["data"])
        assert data == {"volumeLevel": 5}

    @pytest.mark.asyncio
    async def test_set_volume(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_volume("DEV001", 3)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"volumeLevel": 3}

    @pytest.mark.asyncio
    async def test_set_child_lock_enabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_child_lock("DEV001", True)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"childLock": 1}

    @pytest.mark.asyncio
    async def test_set_child_lock_disabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_child_lock("DEV001", False)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"childLock": 0}

    @pytest.mark.asyncio
    async def test_set_auto_lock(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_auto_lock("DEV001", 300)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"autoLock": 300}

    @pytest.mark.asyncio
    async def test_set_extra_dry_enabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_dry("DEV001", True)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"extraDry": True}

    @pytest.mark.asyncio
    async def test_set_extra_dry_disabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_dry("DEV001", False)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"extraDry": False}

    @pytest.mark.asyncio
    async def test_set_cat_delay(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_cat_delay("DEV001", 900)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"catDelay": 900}

    @pytest.mark.asyncio
    async def test_set_cat_sensitivity(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_cat_sensitivity("DEV001", 20)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"catSense": 20}

    @pytest.mark.asyncio
    async def test_set_cleaning_mode_automatic(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_cleaning_mode("DEV001", CleaningMode.AUTOMATIC)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"mode": 0}

    @pytest.mark.asyncio
    async def test_set_cleaning_mode_manual(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_cleaning_mode("DEV001", CleaningMode.MANUAL)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"mode": 1}

    @pytest.mark.asyncio
    async def test_set_schedule(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()
        entries = [
            ScheduleEntry(day=1, hour=8, minute=0, enabled=True),
            ScheduleEntry(day=3, hour=14, minute=30, enabled=True),
        ]

        async with CatGenieClient(creds, session=session) as client:
            await client.set_schedule("DEV001", entries)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {
            "schedule": [
                {"day": 1, "hour": 8, "minute": 0, "enabled": True},
                {"day": 3, "hour": 14, "minute": 30, "enabled": True},
            ]
        }

    @pytest.mark.asyncio
    async def test_set_dnd(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_dnd("DEV001", "22:00", "07:00")

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"dndFrom": "22:00", "dndTo": "07:00"}

    @pytest.mark.asyncio
    async def test_multiple_config_fields(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.update_configuration(
                "DEV001", childLock=1, volumeLevel=5, extraDry=True
            )

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"childLock": 1, "volumeLevel": 5, "extraDry": True}

    @pytest.mark.asyncio
    async def test_set_extra_wash_enabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_wash("DEV001", True)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"binaryElements": {"EXTRA_WASH": True}}

    @pytest.mark.asyncio
    async def test_set_extra_wash_disabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_wash("DEV001", False)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"binaryElements": {"EXTRA_WASH": False}}

    @pytest.mark.asyncio
    async def test_set_extra_shake_enabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_shake("DEV001", True)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"binaryElements": {"EXTRA_SHAKE": True}}

    @pytest.mark.asyncio
    async def test_set_extra_shake_disabled(self) -> None:
        session = _make_mock_session()
        creds = _make_credentials()

        async with CatGenieClient(creds, session=session) as client:
            await client.set_extra_shake("DEV001", False)

        data = json.loads(session.request.call_args[1]["data"])
        assert data == {"binaryElements": {"EXTRA_SHAKE": False}}
