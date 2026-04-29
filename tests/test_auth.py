"""Tests for catgenie.auth — Credentials and CatGenieAuth."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from catgenie.auth import AuthenticationError, Credentials


class TestCredentials:
    def test_defaults(self) -> None:
        creds = Credentials()
        assert creds.access_token == ""
        assert creds.refresh_token == ""
        assert creds.secret == ""
        assert creds.token_expiration == 0.0
        assert creds.account_id == ""
        assert creds.user_id == ""
        assert creds.tenant_id == ""

    def test_is_token_expired_no_token(self) -> None:
        creds = Credentials()
        assert creds.is_token_expired is True

    def test_is_token_expired_past_expiration(self) -> None:
        creds = Credentials(
            access_token="tok",
            token_expiration=time.time() - 1,
        )
        assert creds.is_token_expired is True

    def test_is_token_not_expired(self) -> None:
        creds = Credentials(
            access_token="tok",
            token_expiration=time.time() + 3600,
        )
        assert creds.is_token_expired is False

    def test_with_values(self) -> None:
        creds = Credentials(
            access_token="access",
            refresh_token="refresh",
            secret="s" * 84,
            token_expiration=9999999999.0,
            account_id="acct",
            user_id="user",
            tenant_id="tenant",
        )
        assert creds.access_token == "access"
        assert creds.refresh_token == "refresh"
        assert creds.is_token_expired is False


class TestAuthenticationError:
    def test_is_exception(self) -> None:
        err = AuthenticationError("bad code")
        assert isinstance(err, Exception)
        assert str(err) == "bad code"


class TestCatGenieAuth:
    """Tests that mock curl_cffi — no real network calls."""

    def _make_mock_response(
        self,
        status_code: int = 200,
        content: bytes = b"",
        json_data: dict | None = None,
    ) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.content = content
        resp.text = content.decode() if content else ""
        if json_data is not None:
            resp.json.return_value = json_data
            resp.content = b"data"
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_context_manager_creates_and_closes_session(self) -> None:
        from catgenie.auth import CatGenieAuth

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                assert auth._session is mock_session

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_injected_session_not_closed(self) -> None:
        from catgenie.auth import CatGenieAuth

        mock_session = AsyncMock()
        async with CatGenieAuth(session=mock_session) as auth:
            assert auth._session is mock_session

        mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_base_url_success(self) -> None:
        from catgenie.auth import CatGenieAuth

        resp = self._make_mock_response(
            json_data={"url": "https://iot.petnovations.com", "env": "prod"}
        )

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                result = await auth.get_base_url(61, "499999999")

        assert result["url"] == "https://iot.petnovations.com"

    @pytest.mark.asyncio
    async def test_request_login_code_returns_status(self) -> None:
        from catgenie.auth import CatGenieAuth

        resp = self._make_mock_response(status_code=200, content=b"")

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                result = await auth.request_login_code(61, "499999999")

        assert result["status"] == 200

    @pytest.mark.asyncio
    async def test_login_success(self) -> None:
        from catgenie.auth import CatGenieAuth

        login_data = {
            "accessToken": "access.jwt.token",
            "refreshToken": "refresh.jwt.token",
            "expiration": int(time.time() * 1000) + 1_800_000,
            "accountId": "acct-123",
            "userId": "user-456",
            "tenantId": "tenant-789",
        }
        resp = self._make_mock_response(json_data=login_data)

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                creds = await auth.login(61, "499999999", "123456")

        assert creds.access_token == "access.jwt.token"
        assert creds.refresh_token == "refresh.jwt.token"
        assert creds.account_id == "acct-123"
        assert creds.is_token_expired is False

    @pytest.mark.asyncio
    async def test_login_empty_body_raises_auth_error(self) -> None:
        from catgenie.auth import CatGenieAuth

        resp = self._make_mock_response(status_code=200, content=b"")

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                with pytest.raises(AuthenticationError, match="Login failed"):
                    await auth.login(61, "499999999", "000000")

    @pytest.mark.asyncio
    async def test_login_non_200_raises_auth_error(self) -> None:
        from catgenie.auth import CatGenieAuth

        resp = self._make_mock_response(status_code=401, content=b"")

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                with pytest.raises(AuthenticationError):
                    await auth.login(61, "499999999", "000000")

    @pytest.mark.asyncio
    async def test_refresh_success(self) -> None:
        from catgenie.auth import CatGenieAuth

        refresh_data = {
            "token": "new.access.token",
            "expiration": int(time.time() * 1000) + 1_800_000,
        }
        resp = self._make_mock_response(json_data=refresh_data)

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.request.return_value = resp
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                auth.credentials.refresh_token = "existing.refresh.token"
                creds = await auth.refresh()

        assert creds.access_token == "new.access.token"
        assert creds.is_token_expired is False

    @pytest.mark.asyncio
    async def test_refresh_without_token_raises(self) -> None:
        from catgenie.auth import CatGenieAuth

        with patch("catgenie.auth.AsyncSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            async with CatGenieAuth() as auth:
                with pytest.raises(AuthenticationError, match="No refresh token"):
                    await auth.refresh()

    @pytest.mark.asyncio
    async def test_request_without_context_manager_raises(self) -> None:
        from catgenie.auth import CatGenieAuth

        auth = CatGenieAuth()
        with pytest.raises(RuntimeError, match="context manager"):
            await auth.get_base_url(61, "499999999")
