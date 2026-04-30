"""CatGenie AI API client."""

from .auth import CatGenieAuth, Credentials
from .client import CatGenieClient
from .exceptions import CatGenieAuthenticationError, CatGenieAPIError, CatGenieException
from .models import (
    ActivationInfo,
    APIError,
    BinaryElements,
    CleaningMode,
    Device,
    DeviceConfiguration,
    DeviceStatus,
    HeaterConfig,
    LoginResponse,
    Notification,
    NotificationData,
    NotificationList,
    NotificationServiceType,
    OperationState,
    OperationStatus,
    RefreshResponse,
    ScheduleEntry,
    UpdateGroup,
    WaterConfig,
)
from .signing import encrypt_str1, generate_request_headers

__all__ = [
    # Client
    "CatGenieAuth",
    "CatGenieClient",
    "Credentials",
    # Exceptions
    "CatGenieAuthenticationError",
    "CatGenieAPIError",
    "CatGenieException",
    # Device models
    "ActivationInfo",
    "BinaryElements",
    "CleaningMode",
    "Device",
    "DeviceConfiguration",
    "DeviceStatus",
    "HeaterConfig",
    "OperationState",
    "OperationStatus",
    "ScheduleEntry",
    "UpdateGroup",
    "WaterConfig",
    # Auth models
    "LoginResponse",
    "RefreshResponse",
    # Notification models
    "Notification",
    "NotificationData",
    "NotificationList",
    "NotificationServiceType",
    # Error model
    "APIError",
    # Signing helpers
    "encrypt_str1",
    "generate_request_headers",
]
