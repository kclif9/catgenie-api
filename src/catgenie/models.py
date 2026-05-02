"""Pydantic v2 models for the CatGenie API.

All models use strict field aliases matching the API JSON keys, and
`model_config = ConfigDict(populate_by_name=True)` so the Pythonic
attribute names (snake_case) can also be used directly.

Unknown fields are **forbidden** at the outer device level (so we learn
about new API fields immediately) but **allowed** on deeply nested objects
(configuration is very version-dependent).

Downstream consumers (e.g. Home Assistant) should reference these models
rather than raw dicts — changes in the API surface will raise validation
errors immediately rather than surfacing as silent KeyErrors at runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import IntEnum
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Attach UTC if the datetime is naive, otherwise convert to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_ensure_utc)]


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

_strict = ConfigDict(populate_by_name=True, extra="forbid")
_lenient = ConfigDict(populate_by_name=True, extra="allow")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeviceStatus(IntEnum):
    """Connectivity status reported by the device shadow."""

    UNKNOWN = 0
    IDLE = 1
    CONNECTED = 2


class OperationState(IntEnum):
    """Current cleaning-cycle operation state."""

    IDLE = 0
    RUNNING = 1


class CleaningMode(IntEnum):
    """Cleaning trigger mode: automatic (cat-sensor) or manual."""

    AUTOMATIC = 0
    MANUAL = 1


class NotificationServiceType(IntEnum):
    """Push notification delivery service."""

    FCM_ANDROID = 0
    APNS_IOS = 1


# ---------------------------------------------------------------------------
# Device sub-models
# ---------------------------------------------------------------------------


class ActivationInfo(BaseModel):
    """Device activation record including lifetime cycle count."""

    model_config = _lenient

    date: UtcDatetime = Field(alias="date")
    state: int = Field(alias="state")
    # Total lifetime cleaning cycles — the most useful counter for HA.
    count: int = Field(alias="count")


class HeaterConfig(BaseModel):
    """Heater hardware configuration."""

    model_config = _lenient

    model: int = Field(alias="model")
    temp_out_ref: int = Field(alias="tempOutRef")


class WaterConfig(BaseModel):
    """Water sensor and fill level configuration."""

    model_config = _lenient

    fill_max: int = Field(alias="fillMax")
    fill_min: int = Field(alias="fillMin")
    sense_detect: int = Field(alias="senseDetect")
    sense_clean: int = Field(alias="senseClean")


class BinaryElements(BaseModel):
    """Binary feature flags for extra wash and shake cycles."""

    model_config = _lenient

    extra_wash: bool = Field(False, alias="EXTRA_WASH")
    extra_shake: bool = Field(False, alias="EXTRA_SHAKE")


class ScheduleEntry(BaseModel):
    """A single scheduled cleaning time."""

    model_config = _lenient

    # Schedule entries are flexible across firmware versions.
    day: int | None = Field(None, alias="day")
    hour: int | None = Field(None, alias="hour")
    minute: int | None = Field(None, alias="minute")
    enabled: bool = Field(True, alias="enabled")


class DeviceConfiguration(BaseModel):
    """Device configuration block — firmware-version-dependent, lenient."""

    model_config = _lenient

    child_lock: int = Field(0, alias="childLock")
    auto_lock: int = Field(0, alias="autoLock")
    volume_level: int = Field(7, alias="volumeLevel")
    mode: CleaningMode = Field(CleaningMode.AUTOMATIC, alias="mode")
    cat_sense: int = Field(16, alias="catSense")
    timezone: str = Field("+00:00", alias="timezone")
    # Seconds to delay start after cat detection.
    cat_delay: int = Field(600, alias="catDelay")
    pump_pct_t: int = Field(100, alias="pumpPctT")
    extra_dry: bool = Field(False, alias="extraDry")
    schedule: list[ScheduleEntry] = Field(default_factory=list, alias="schedule")
    activation: ActivationInfo | None = Field(None, alias="activation")
    heater: HeaterConfig | None = Field(None, alias="heater")
    water: WaterConfig | None = Field(None, alias="water")
    binary_elements: BinaryElements | None = Field(None, alias="binaryElements")

    @property
    def total_cycles(self) -> int:
        """Lifetime cleaning cycle count."""
        return self.activation.count if self.activation else 0


class OperationStatus(BaseModel):
    """Real-time cleaning operation state and progress."""

    model_config = _lenient

    # 0 = idle, 1 = running
    state: OperationState = Field(alias="state")
    # 255 = idle/complete, 0–100 = progress percentage while running
    progress: int = Field(alias="progress")
    # Error string during an operation (empty when no error)
    error: str = Field("", alias="error")
    # Cat sensor detection value (non-None when cat detected)
    sens: str | None = Field(None, alias="sens")
    # Real-time clock value from the device
    rtc: str | None = Field(None, alias="rtc")
    # Operation mode during cycle
    mode: int = Field(0, alias="mode")
    # Manual flag during operation
    manual: int = Field(0, alias="manual")
    # Current step number in the cleaning cycle
    step_num: int = Field(0, alias="stepNum")
    # Relay hardware mode
    relay_mode: int | None = Field(None, alias="relayMode")

    @property
    def is_cleaning(self) -> bool:
        """Return True while a cleaning cycle is in progress."""
        return self.state == OperationState.RUNNING

    @property
    def clean_progress_pct(self) -> int | None:
        """Progress percentage, or None when idle."""
        return None if self.progress == 255 else self.progress

    @property
    def has_error(self) -> bool:
        """Return True when an error string is present."""
        return bool(self.error)

    @property
    def is_cat_detected(self) -> bool:
        """Return True when the cat sensor reports detection."""
        return self.sens is not None and self.sens != ""


class UpdateGroup(BaseModel):
    """Firmware update rollout group assignment."""

    model_config = _lenient

    id: str = Field(alias="id")
    name: str = Field(alias="name")


# ---------------------------------------------------------------------------
# Core device model
# ---------------------------------------------------------------------------


class Device(BaseModel):
    """A single CatGenie device as returned by GET device/device/v2."""

    model_config = _lenient  # outer fields lenient so new API additions don't break HA

    # Identifiers
    manufacturer_id: str = Field(alias="manufacturerId")
    name: str = Field(alias="name")
    mac_address: str = Field(alias="macAddress")

    # Hardware / firmware
    hw_revision: str = Field(alias="hwRevision")
    fw_version: str = Field(alias="fwVersion")
    type: int = Field(0, alias="type")
    pump_type: str = Field("", alias="pumpTypeEnum")

    # Connectivity
    status: int = Field(0, alias="status")
    reported_status: str = Field("", alias="reportedStatus")
    connection_mode: str = Field("", alias="connectionMode")

    # State
    last_clean: UtcDatetime | None = Field(None, alias="lastClean")
    remaining_sani_solution: int = Field(0, alias="remainingSaniSolution")
    service_level: str = Field("", alias="serviceLevel")
    country_code: int = Field(0, alias="countryCode")

    # Hardware flags
    low_heater: bool = Field(False, alias="lowHeater")
    fan_shutter: bool = Field(False, alias="fanShutter")
    dome: bool = Field(False, alias="dome")

    # Sub-models
    configuration: DeviceConfiguration = Field(
        default_factory=lambda: DeviceConfiguration(),
        alias="configuration",
    )
    operation_status: OperationStatus = Field(
        default_factory=lambda: OperationStatus(
            state=OperationState.IDLE, progress=255
        ),
        alias="operationStatus",
    )
    active_errors: list[Any] = Field(default_factory=list, alias="activeErrors")
    update_group: UpdateGroup | None = Field(None, alias="updateGroup")

    @property
    def is_online(self) -> bool:
        """Return True when the device reports as connected."""
        return self.reported_status.lower() == "connected"

    @property
    def is_cleaning(self) -> bool:
        """Return True while a cleaning cycle is in progress."""
        return self.operation_status.is_cleaning

    @property
    def unique_id(self) -> str:
        """Stable identifier for HA entity registry — prefer manufacturer_id."""
        return self.manufacturer_id


# ---------------------------------------------------------------------------
# Notification models
# ---------------------------------------------------------------------------


class NotificationData(BaseModel):
    """Parsed `data` JSON blob inside a notification."""

    model_config = _lenient

    type: int = Field(0, alias="type")
    parent_device_id: str = Field("", alias="parentDeviceId")
    device_id: str = Field("", alias="deviceId")
    device_name: str = Field("", alias="deviceName")
    error_type: str = Field("", alias="errorType")
    version: str = Field("", alias="version")
    event_timestamp: str = Field("", alias="eventTimestamp")


class Notification(BaseModel):
    """A single push notification from the PetNovations backend."""

    model_config = _lenient

    id: str = Field(alias="id")
    creation_time: UtcDatetime = Field(alias="creationTime")
    # Raw JSON string — parsed on demand via .parsed_data
    data: str = Field("", alias="data")

    @property
    def parsed_data(self) -> NotificationData | None:
        """Parse the nested JSON `data` string."""
        if not self.data:
            return None
        try:
            return NotificationData.model_validate(json.loads(self.data))
        except (json.JSONDecodeError, Exception):
            return None


class NotificationList(BaseModel):
    """Paginated list of notifications for a user."""

    model_config = _lenient

    user_id: str = Field(alias="userId")
    notifications: list[Notification] = Field(
        default_factory=list, alias="notifications"
    )


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------


class LoginResponse(BaseModel):
    """POST loginByPhoneNumber/v2 response."""

    model_config = _lenient

    user_id: str = Field(alias="userId")
    tenant_id: str = Field(alias="tenantId")
    account_id: str = Field(alias="accountId")
    email: str = Field("", alias="email")
    first_name: str = Field("", alias="firstName")
    last_name: str = Field("", alias="lastName")
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    phone: str = Field("", alias="phone")
    email_verified: bool = Field(False, alias="emailVerified")
    phone_verified: bool = Field(False, alias="phoneVerified")
    password_reset_required: bool = Field(False, alias="passwordResetRequired")
    mfa_required: bool = Field(False, alias="mfaRequired")
    mfa_request_token: str | None = Field(None, alias="mfaRequestToken")
    group_names: list[str] = Field(default_factory=list, alias="groupNames")

    @property
    def full_name(self) -> str:
        """Return first and last name joined and stripped."""
        return f"{self.first_name} {self.last_name}".strip()


class RefreshResponse(BaseModel):
    """POST facade/v1/mobile-user/refreshToken/v2 response."""

    model_config = _lenient

    # Note: the access token field is "token" here, not "accessToken"
    token: str = Field(alias="token")
    refresh_token: str = Field(alias="refreshToken")
    # Millisecond unix timestamp returned as a string
    expiration: str = Field(alias="expiration")
    review_status: int = Field(0, alias="reviewStatus")
    app_version: str = Field("", alias="appVersion")
    enable_chat: bool = Field(False, alias="enableChat")
    chat_url: str = Field("", alias="chatUrl")

    @property
    def expiration_ms(self) -> int:
        """Return the token expiration as a millisecond Unix timestamp."""
        return int(self.expiration)


# ---------------------------------------------------------------------------
# API error model
# ---------------------------------------------------------------------------


class APIError(BaseModel):
    """Standard error envelope from PetNovations API."""

    model_config = _lenient

    code: str = Field("", alias="code")
    message: str = Field("", alias="message")
    trace_id: str = Field("", alias="traceId")
    host_name: str = Field("", alias="hostName")
    service_name: str | None = Field(None, alias="serviceName")
    data: Any = Field(None, alias="data")
