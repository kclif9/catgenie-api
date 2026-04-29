# GitHub Copilot Instructions for CatGenie API

## Project Overview
The CatGenie API is a reverse-engineered Python library for interacting with the CatGenie AI smart litter box by PetNovations. It provides authentication (phone number + SMS OTP), device status, and control (start/stop cleaning cycles). The library targets Home Assistant integration and is designed for platinum-level quality from day one.

## Critical Infrastructure Knowledge

### TLS Fingerprinting
**The single most important non-obvious fact about this API:**
PetNovations' CloudFront edge silently returns `200 OK / Content-Length: 0` for any request whose TLS JA3 fingerprint doesn't match a mobile/browser client. Python stdlib SSL (urllib, http.client, requests, aiohttp) is **silently filtered** — the server returns an empty 200 but never sends the SMS and never returns data.

**Solution**: All HTTP must use `curl_cffi` with `impersonate="chrome131_android"` (`TLS_IMPERSONATE` constant). This is non-negotiable. Never replace `curl_cffi` with any other HTTP library.

### Authentication Flow
1. `GET config/v1/url` — preflight (mirrors real app behaviour)
2. `POST ums/v1/users/generateLoginCode/v2` — triggers SMS; body: `{"str1": "<AES-encrypted phone>"}`
3. `POST ums/v1/users/loginByPhoneNumber/v2` — exchanges phone + code for JWT + refresh token
4. `POST facade/v1/mobile-user/refreshToken/v2` — refresh; access token ~30 min, refresh token ~10 years

### Request Headers
Every request requires:
- `x-pm-en-dec`: AES-CBC(timestamp, static_key, zero_iv) — implemented in `signing.py`
- `x-pm-en-ver`: `"1.0.0"`
- `x-render-t`: `"{path}/{timestamp_ms}"` — `facade/v1/` prefix is stripped
- `y-pm-sg-b` / `y-pm-sg-p`: HMAC-SHA256 body/params signatures (only when 84-char secret is available; server does **not** validate these)

### Phone Encryption
`str1` = AES-CBC(`"+{countryCode}{phone}-{8_random_chars}"`, key=`P-3Rp6d81Kw9a3Z-CyvWH0WXRieyITk6`, iv=zero) — see `signing.encrypt_str1()`.

---

## Core Development Principles

### 1. Code Quality Standards
- **Type Safety**: Full type hints everywhere. Package ships `py.typed` (PEP 561). mypy must pass with zero errors.
- **Error Handling**: Fail-fast for critical operations, graceful degradation for non-critical
- **Documentation**: All public APIs must have Google-style docstrings
- **Testing**: Write tests for new features and bug fixes

### 2. Pre-commit Compliance
**CRITICAL**: All code must pass pre-commit checks before committing. Run:
```bash
pre-commit run --all-files
```

Our pre-commit pipeline includes:
- **ruff**: Linting and auto-formatting (E, F, W, I rules)
- **mypy**: Type checking (config in `pyproject.toml` `[tool.mypy]`)
- **pydocstyle**: Google convention docstrings
- **File hygiene**: trailing whitespace, line endings, YAML/TOML/JSON validation

### 3. Exception Handling Philosophy

**Fail Fast (raise exceptions):**
- Authentication failures (`AuthenticationError`)
- API communication errors (non-200 responses)
- Control command failures (start/stop cleaning)
- Missing required configuration
- Invalid API responses that break core functionality

**Graceful Degradation (log and continue):**
- Missing optional device fields (use Pydantic defaults)
- Firmware-version-dependent configuration fields (use `extra="allow"` on lenient models)
- Non-critical nested component parsing

**Example Pattern:**
```python
# Critical — fail fast
async def login(self, country_code: int, phone: str, code: str) -> Credentials:
    resp = await self._request("POST", ENDPOINT_LOGIN_BY_PHONE, body=body)
    if resp.status_code != 200 or not resp.content:
        raise AuthenticationError(
            f"Login failed (status={resp.status_code}). "
            "SMS code is likely expired or already consumed."
        )
    ...

# Non-critical — Pydantic handles gracefully via Field(default=...)
class DeviceConfiguration(BaseModel):
    model_config = _lenient  # extra="allow" — unknown firmware fields are accepted
    child_lock: int = Field(0, alias="childLock")
    ...
```

### 4. Code Architecture

**Project Structure:**
```
src/catgenie/
├── __init__.py     # Public API exports
├── py.typed        # PEP 561 marker — do not remove
├── auth.py         # Phone + SMS authentication (CatGenieAuth, Credentials)
├── client.py       # High-level async client (CatGenieClient)
├── const.py        # Constants, endpoints, TLS_IMPERSONATE
├── models.py       # Pydantic v2 models for all API responses
└── signing.py      # AES encryption + HMAC request signing
```

**Design Patterns:**
- **Pydantic v2 Models**: All API responses parsed into typed models. Never return raw dicts from public methods.
- **Two model configs**: `_strict` (`extra="forbid"`) for outer/core models, `_lenient` (`extra="allow"`) for firmware-dependent nested config.
- **Type Safety**: Full type hints, `py.typed` marker, mypy zero-error.
- **Async/Await**: All I/O is async. Both `CatGenieAuth` and `CatGenieClient` are async context managers.
- **Shared session injection**: Both classes accept an optional `AsyncSession[Response]` so the HA integration can share one session.

### 5. Common Patterns and Best Practices

#### Pydantic Models (v2 style)
```python
from pydantic import BaseModel, ConfigDict, Field

_strict = ConfigDict(populate_by_name=True, extra="forbid")
_lenient = ConfigDict(populate_by_name=True, extra="allow")

class Device(BaseModel):
    """A CatGenie device as returned by GET device/device/v2."""
    model_config = _lenient

    manufacturer_id: str = Field(alias="manufacturerId")
    name: str = Field(alias="name")
    fw_version: str = Field(alias="fwVersion")

    @property
    def is_online(self) -> bool:
        return self.reported_status.lower() == "connected"
```

#### HTTP Requests (curl_cffi — always impersonate)
```python
from curl_cffi.requests import AsyncSession, Response
from .const import TLS_IMPERSONATE

# Session construction
self._session: AsyncSession[Response] | None = AsyncSession(impersonate=TLS_IMPERSONATE)

# Every request must pass impersonate=
resp = await self._session.request(
    method, url, headers=headers, data=data, params=params,
    impersonate=TLS_IMPERSONATE,
)
```

#### Logging
```python
import logging

_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("Detailed debug info")
_LOGGER.info("Key state changes")
_LOGGER.warning("Recoverable issues — missing optional data")
_LOGGER.error("Failures requiring attention", exc_info=True)
```

#### Async Context Manager Pattern
```python
from types import TracebackType

async def __aenter__(self) -> CatGenieClient:
    if self._session is None:
        self._session = AsyncSession(impersonate=TLS_IMPERSONATE)
    return self

async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    if self._owns_session and self._session is not None:
        await self._session.close()
        self._session = None
```

### 6. Testing Requirements

When adding new features:
1. Write unit tests in `tests/`
2. Test both success and failure paths
3. Mock curl_cffi `AsyncSession` — do NOT use real HTTP in unit tests
4. Verify `AuthenticationError` is raised on empty-body 200 responses (the TLS-filtered response shape)

### 7. Documentation Standards

**Module Docstrings:**
```python
"""Brief module description.

Longer description explaining the module's purpose, key classes,
and how it fits into the overall architecture.
"""
```

**Function/Method Docstrings:**
```python
async def get_devices(self) -> list[Device]:
    """Get all devices associated with the account.

    Returns:
        List of Device models.

    Raises:
        AuthenticationError: If the access token is invalid and refresh fails.
        HTTPError: If the API returns a non-2xx response.
    """
```

### 8. Common Gotchas and Anti-Patterns

**❌ DON'T:**
- Replace `curl_cffi` with `aiohttp`, `httpx`, `requests`, or urllib — TLS fingerprinting will break
- Use bare `AsyncSession` without `[Response]` type argument — violates `disallow_any_generics`
- Pass `method` as a plain `str` to `session.request()` — use `_HttpMethod = Literal["GET", "POST", ...]`
- Use `extra="forbid"` on `DeviceConfiguration` — firmware updates add unknown fields
- Remove `py.typed` — breaks downstream type checking in the HA integration
- Catch exceptions without re-raising or logging with `exc_info=True`
- Use bare `except:` clauses
- Leave TODO comments without GitHub issues
- Commit code that fails pre-commit checks

**✅ DO:**
- Always pass `impersonate=TLS_IMPERSONATE` on every curl_cffi request
- Use `cast(dict[str, Any], resp.json())` when curl_cffi's untyped `json()` is called and you need a typed return
- Annotate `AsyncSession` as `AsyncSession[Response]`
- Use `_strict` config for outer models, `_lenient` for firmware-version-dependent nested objects
- Use `_LOGGER` instead of `print()` statements
- Run `pre-commit run --all-files` before committing

### 9. Version Compatibility

- **Python**: >= 3.10 (as declared in `pyproject.toml`; target HA 2024.x+)
- **Dependencies**:
  - `curl_cffi >= 0.7`: TLS-impersonating HTTP client — **not negotiable**
  - `pydantic >= 2.0`: Data validation and typing
  - `pycryptodome >= 3.20`: AES-CBC encryption for request signing
- **mypy config**: lives in `pyproject.toml` `[tool.mypy]` — there is no `mypy.ini`

### 10. API Client Best Practices

**Session Injection (for HA integration):**
```python
# HA integration can inject a shared session:
async with CatGenieAuth(session=shared_session) as auth:
    creds = await auth.login(...)

async with CatGenieClient(creds, session=shared_session) as client:
    devices = await client.get_devices()
```

**Token Management:**
- Access tokens expire in ~30 minutes; refresh tokens are ~10 years
- `CatGenieClient._request()` auto-refreshes on 401 if a `CatGenieAuth` is attached via `set_auth()`
- `Credentials.is_token_expired` checks expiry before each request

**Model Validation at API Boundaries:**
- `get_devices()` returns `list[Device]` — validated via `Device.model_validate(d)`
- `get_notifications()` returns `NotificationList` — validated via `NotificationList.model_validate(data)`
- All other endpoints return `dict[str, Any]` until models are added — add models as needed

### 11. Making Changes Checklist

Before proposing any code changes:
1. ✅ Understand the TLS fingerprinting requirement — never change the HTTP client
2. ✅ Understand the fail-fast vs graceful degradation philosophy
3. ✅ Check if similar patterns exist in the codebase
4. ✅ Add appropriate type hints (`AsyncSession[Response]`, `_HttpMethod`, etc.)
5. ✅ Write Google-style docstrings
6. ✅ Add error handling following project patterns
7. ✅ Run `pre-commit run --all-files`
8. ✅ Run `mypy src/` and confirm zero errors
9. ✅ Test with `pytest` if tests exist
10. ✅ Update documentation if changing public API

### 12. Contact and Resources

- **Repository**: https://github.com/kclif9/catgenieapi
- **Issues**: Report bugs and feature requests on GitHub
- **Home Assistant Integration**: Designed for HA compatibility
- **API Documentation**: See `API.md` and `capture.md` for reverse-engineered endpoint details

---

## Development Workflow

### Virtual Environment
**CRITICAL**: This project uses `uv`. Always use the venv directly:
```bash
# Run commands via venv (preferred)
.venv/bin/python ...
.venv/bin/pytest ...

# Or activate
source .venv/bin/activate
```

### Before Completing Any Work
**MANDATORY**: Before considering any work complete, you MUST:
1. ✅ Run the full test suite with coverage (`.venv/bin/pytest --cov=src --cov-report=term-missing`)
2. ✅ Verify test coverage has not regressed
3. ✅ Run all pre-commit checks (`pre-commit run --all-files`)
4. ✅ Run mypy and confirm zero errors (`.venv/bin/python -m mypy src/catgenie/`)
5. ✅ Ensure ALL tests pass and ALL checks pass

**Do NOT claim work is complete until all tests pass, all checks pass, and mypy is clean.**

---

## Quick Reference Commands

```bash
# Install in editable mode with dev dependencies
.venv/bin/pip install -e ".[dev]"

# Run ALL tests (required before completing work)
.venv/bin/pytest

# Run tests with coverage report (required before completing work)
.venv/bin/pytest --cov=src --cov-report=term-missing

# Run pre-commit checks (required before completing work)
pre-commit run --all-files

# Install pre-commit hooks
pre-commit install

# Type checking (must return zero errors)
.venv/bin/python -m mypy src/catgenie/

# Format code
.venv/bin/ruff format .

# Lint and auto-fix
.venv/bin/ruff check --fix .
```

---

## When Working on This Project

**Always consider:**
1. Will this change break the TLS fingerprint requirement? (Never swap curl_cffi)
2. Will this break existing HA integrations?
3. Does this follow the project's exception handling philosophy?
4. Will this pass all pre-commit checks and mypy?
5. Is the code type-safe, well-documented, and using the correct model config (`_strict` vs `_lenient`)?

**Completion Checklist (MANDATORY):**
1. ✅ All tests pass (`.venv/bin/pytest` returns 0 exit code)
2. ✅ Test coverage verified and not regressed
3. ✅ All pre-commit checks pass
4. ✅ mypy reports zero errors (`.venv/bin/python -m mypy src/catgenie/`)
5. ✅ No new warnings or errors introduced

**Remember**: This library controls a physical device in people's homes. Reliability and correctness are paramount. A bug in `start_cleaning()` or auth refresh runs a litter box at 3am. Fail fast, log clearly, and never silently swallow errors.
