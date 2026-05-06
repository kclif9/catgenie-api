# catgenie-api

A reverse-engineered async Python library for the [CatGenie AI](https://www.catgenie.com/) smart litter box by PetNovations. Provides full authentication, device status, and cleaning cycle control — designed as the foundation for a Home Assistant integration.

## Features

- **Phone + SMS authentication** — full login flow using the same OTP mechanism as the official app
- **Automatic token refresh** — access tokens (~30 min) are transparently refreshed using the long-lived refresh token (~10 years)
- **Device status & control** — start/stop cleaning cycles, read configuration, operation state, and sani-solution level
- **Fully typed Pydantic v2 models** — every API response is validated into typed Python objects; no raw dicts
- **PEP 561 compliant** — ships `py.typed`, zero mypy errors with strict settings
- **Home Assistant ready** — async context managers, shared session injection, and a clean model hierarchy that maps directly to HA entities

## How It Works

The CatGenie app communicates with `iot.petnovations.com` (CloudFront-fronted AWS API Gateway). Every request requires three custom headers derived from an AES-CBC encrypted timestamp and HMAC-SHA256 signatures. The phone number itself is AES-encrypted in the auth request body.

There is one significant non-obvious requirement: **PetNovations' edge silently discards requests from Python's standard SSL stack**, returning `200 OK` with an empty body instead of sending the SMS or returning data. This library uses [`curl_cffi`](https://github.com/yifeikong/curl_cffi) to impersonate a Chrome Android TLS fingerprint, which is the only way to reliably trigger the SMS and receive API responses.

## Installation

```bash
pip install catgenie
```

Or for development:

```bash
git clone https://github.com/kclif9/catgenieapi
cd catgenie-api
pip install -e ".[dev]"
```

## Usage

### Authentication

```python
import asyncio
from catgenie import CatGenieAuth, CatGenieClient

async def main():
    auth = CatGenieAuth()
    # Step 1 — trigger SMS to the phone number
    await auth.request_login_code(country_code=61, phone="499999999")

    # Step 2 — exchange the SMS code for tokens
    code = input("Enter SMS code: ")
    credentials = await auth.login(country_code=61, phone="499999999", code=code)
    await auth.async_close()

    # Step 3 — use the client
    client = CatGenieClient(credentials)
    try:
        devices = await client.get_devices()
        for device in devices:
            print(f"{device.name}: {'online' if device.is_online else 'offline'}")
            print(f"  Sani-solution remaining: {device.remaining_sani_solution}%")
            print(f"  Lifetime cycles: {device.configuration.total_cycles}")
    finally:
        await client.async_close()

asyncio.run(main())
```

### Controlling a Device

```python
client = CatGenieClient(credentials)
try:
    devices = await client.get_devices()
    device = devices[0]

    # Start a cleaning cycle
    await client.start_cleaning(device.manufacturer_id)

    # Stop a cleaning cycle
    await client.stop_cleaning(device.manufacturer_id)
finally:
    await client.async_close()
```

### Token Persistence

```python
import json, dataclasses
from catgenie import Credentials

# Save after login
with open("credentials.json", "w") as f:
    json.dump(dataclasses.asdict(credentials), f)

# Restore on next run
with open("credentials.json") as f:
    credentials = Credentials(**json.load(f))
```

### Shared Session (Home Assistant pattern)

```python
from curl_cffi.requests import AsyncSession, Response
from catgenie import CatGenieAuth, CatGenieClient
from catgenie.const import TLS_IMPERSONATE

session = AsyncSession(impersonate=TLS_IMPERSONATE)
try:
    auth = CatGenieAuth(session=session)
    credentials = await auth.login(...)

    client = CatGenieClient(credentials, session=session)
    devices = await client.get_devices()
finally:
    await session.close()
```

## API Reference

### `CatGenieAuth`

| Method | Description |
|---|---|
| `get_base_url(country_code, phone)` | Preflight config call (mirrors app behaviour) |
| `request_login_code(country_code, phone)` | Triggers SMS OTP to the phone number |
| `login(country_code, phone, code)` | Exchanges OTP for `Credentials` |
| `refresh()` | Refreshes the access token using the refresh token |

### `CatGenieClient`

| Method | Returns | Description |
|---|---|---|
| `get_devices()` | `list[Device]` | All devices on the account |
| `get_device_status(device_id)` | `dict` | Raw operation status |
| `start_cleaning(device_id)` | `dict` | Start a cleaning cycle |
| `stop_cleaning(device_id)` | `dict` | Stop a cleaning cycle |
| `get_account()` | `dict` | User profile |
| `get_pets()` | `list[dict]` | Pet profiles |
| `get_pet_statistics()` | `dict` | Per-pet usage statistics |
| `get_notifications()` | `NotificationList` | Push notification history |
| `get_notification_settings()` | `dict` | Push notification preferences |
| `get_firmware_info(manufacturer_id)` | `dict` | Available firmware update |
| `get_mainboard(manufacturer_id)` | `dict` | Mainboard hardware info |

### Key Models

| Model | Notable properties |
|---|---|
| `Device` | `unique_id`, `name`, `is_online`, `is_cleaning`, `remaining_sani_solution`, `last_clean`, `fw_version` |
| `DeviceConfiguration` | `total_cycles`, `mode` (`CleaningMode`), `cat_delay`, `schedule`, `binary_elements` |
| `OperationStatus` | `is_cleaning`, `clean_progress_pct` (0–100 while running, `None` when idle) |
| `ActivationInfo` | `count` (lifetime cleaning cycles), `date` (first activation) |
| `Notification` / `NotificationData` | `parsed_data` property auto-parses the nested JSON payload |
| `Credentials` | `access_token`, `refresh_token`, `is_token_expired` |

## Project Structure

```
src/catgenie/
├── __init__.py     # Public API exports
├── py.typed        # PEP 561 marker
├── auth.py         # Phone + SMS authentication (CatGenieAuth, Credentials)
├── client.py       # High-level async client (CatGenieClient)
├── const.py        # Constants and all endpoint paths
├── models.py       # Pydantic v2 models for every API response
└── signing.py      # AES-CBC encryption + HMAC-SHA256 request signing
```

## Prior Art & Credits

- [Rukongai/CatDjinni](https://github.com/Rukongai/CatDjinni) — reverse engineering research: signing algorithm, Frida scripts
- [appkins/hass-catgenie](https://github.com/appkins/hass-catgenie) — earlier HA integration (requires manual refresh token)
- [PrimeAutomation/petnovations](https://github.com/PrimeAutomation/petnovations) — earlier HA integration (same limitation)

## License

MIT
