"""Constants for the CatGenie API."""

from typing import Literal

BASE_URL = "https://iot.petnovations.com"

# curl_cffi impersonation target — this is REQUIRED.
# PetNovations' edge silently 200-drops requests whose TLS JA3 fingerprint
# isn't a mobile/browser client (Python stdlib SSL is filtered). The Android
# Chrome fingerprint is the closest publicly available match to okhttp+Conscrypt
# and reliably triggers SMS / accepts auth.
TLS_IMPERSONATE: Literal["chrome131_android"] = "chrome131_android"

# Android app User-Agent (confirmed from packet capture)
DEFAULT_HEADERS = {
    "User-Agent": "okhttp/4.9.2",
    "accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "accept-language": "en-AU",
    "Content-Type": "application/json",
    "Connection": "Keep-Alive",
}

# --- Auth endpoints (no JWT required) ---
ENDPOINT_CONFIG_URL = "config/v1/url"
ENDPOINT_GENERATE_LOGIN_CODE = "ums/v1/users/generateLoginCode/v2"
ENDPOINT_LOGIN_BY_PHONE = "ums/v1/users/loginByPhoneNumber/v2"

# --- Token management ---
ENDPOINT_REFRESH_TOKEN = "facade/v1/mobile-user/refreshToken/v2"

# --- Device endpoints ---
ENDPOINT_DEVICES = "device/device/v2"
ENDPOINT_DEVICE_STATUS = "device/management/{device_id}/operation/status"
ENDPOINT_DEVICE_OPERATION = "device/management/{device_id}/operation"
ENDPOINT_DEVICE_CONFIG = "device/management/{device_id}/configuration"
ENDPOINT_DEVICE_THING = "device/v1/thing/{manufacturer_id}"
ENDPOINT_MAINBOARD = "device/mainBoard/{manufacturer_id}"

# --- Notification endpoints ---
ENDPOINT_NOTIFICATIONS = "notification/v1/push/user"
ENDPOINT_NOTIFICATION_SETTINGS = "notification/v1/push/settings"

# --- User/Account endpoints ---
ENDPOINT_USER = "ums/v1/users"
ENDPOINT_PETS = "device/pet/user"
ENDPOINT_PET_STATS = "device/history/account/pet/statistics"

# --- Firmware ---
ENDPOINT_FIRMWARE_UPDATE = "device/update/{manufacturer_id}"
ENDPOINT_FIRMWARE_COMMENTS = "device/update/versions/comments"
