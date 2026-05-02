"""Tests for catgenie.models — Pydantic v2 model validation."""

from __future__ import annotations

from datetime import datetime


from catgenie.models import (
    APIError,
    BinaryElements,
    CleaningMode,
    Device,
    DeviceConfiguration,
    DeviceStatus,
    HeaterConfig,
    LoginResponse,
    Notification,
    NotificationList,
    NotificationServiceType,
    OperationState,
    OperationStatus,
    RefreshResponse,
    ScheduleEntry,
    WaterConfig,
)
from tests.conftest import FULL_DEVICE_PAYLOAD, NOTIFICATION_PAYLOAD


class TestEnums:
    def test_device_status_values(self) -> None:
        assert DeviceStatus.UNKNOWN == 0
        assert DeviceStatus.IDLE == 1
        assert DeviceStatus.CONNECTED == 2

    def test_operation_state_values(self) -> None:
        assert OperationState.IDLE == 0
        assert OperationState.RUNNING == 1

    def test_cleaning_mode_values(self) -> None:
        assert CleaningMode.AUTOMATIC == 0
        assert CleaningMode.MANUAL == 1

    def test_notification_service_type_values(self) -> None:
        assert NotificationServiceType.FCM_ANDROID == 0
        assert NotificationServiceType.APNS_IOS == 1


class TestOperationStatus:
    def test_idle_state(self) -> None:
        s = OperationStatus.model_validate({"state": 0, "progress": 255})
        assert s.state == OperationState.IDLE
        assert s.is_cleaning is False
        assert s.clean_progress_pct is None

    def test_running_state(self) -> None:
        s = OperationStatus.model_validate({"state": 1, "progress": 42})
        assert s.state == OperationState.RUNNING
        assert s.is_cleaning is True
        assert s.clean_progress_pct == 42

    def test_progress_zero_is_not_none(self) -> None:
        s = OperationStatus.model_validate({"state": 1, "progress": 0})
        assert s.clean_progress_pct == 0

    def test_extra_fields_allowed(self) -> None:
        s = OperationStatus.model_validate(
            {"state": 0, "progress": 255, "unexpected": True}
        )
        assert s.state == OperationState.IDLE

    def test_error_field(self) -> None:
        s = OperationStatus.model_validate(
            {"state": 1, "progress": 50, "error": "HEATER_FAULT"}
        )
        assert s.error == "HEATER_FAULT"
        assert s.has_error is True

    def test_no_error(self) -> None:
        s = OperationStatus.model_validate({"state": 0, "progress": 255})
        assert s.error == ""
        assert s.has_error is False

    def test_sens_field_detected(self) -> None:
        s = OperationStatus.model_validate({"state": 0, "progress": 255, "sens": "1"})
        assert s.sens == "1"
        assert s.is_cat_detected is True

    def test_sens_field_not_detected(self) -> None:
        s = OperationStatus.model_validate({"state": 0, "progress": 255})
        assert s.sens is None
        assert s.is_cat_detected is False

    def test_sens_empty_string_not_detected(self) -> None:
        s = OperationStatus.model_validate({"state": 0, "progress": 255, "sens": ""})
        assert s.is_cat_detected is False

    def test_step_num_field(self) -> None:
        s = OperationStatus.model_validate({"state": 1, "progress": 30, "stepNum": 5})
        assert s.step_num == 5

    def test_relay_mode_field(self) -> None:
        s = OperationStatus.model_validate(
            {"state": 0, "progress": 255, "relayMode": 2}
        )
        assert s.relay_mode == 2

    def test_rtc_field(self) -> None:
        s = OperationStatus.model_validate(
            {"state": 0, "progress": 255, "rtc": "2026-01-01T00:00:00"}
        )
        assert s.rtc == "2026-01-01T00:00:00"

    def test_mode_and_manual_fields(self) -> None:
        s = OperationStatus.model_validate(
            {"state": 1, "progress": 10, "mode": 1, "manual": 1}
        )
        assert s.mode == 1
        assert s.manual == 1

    def test_all_fields_from_api(self) -> None:
        s = OperationStatus.model_validate(
            {
                "state": 1,
                "progress": 75,
                "error": "",
                "sens": "1",
                "rtc": "2026-05-01T12:00:00",
                "mode": 0,
                "manual": 0,
                "stepNum": 3,
                "relayMode": 1,
            }
        )
        assert s.is_cleaning is True
        assert s.clean_progress_pct == 75
        assert s.has_error is False
        assert s.is_cat_detected is True
        assert s.step_num == 3
        assert s.relay_mode == 1


class TestDeviceConfiguration:
    def test_defaults(self) -> None:
        cfg = DeviceConfiguration()
        assert cfg.child_lock == 0
        assert cfg.mode == CleaningMode.AUTOMATIC
        assert cfg.cat_delay == 600
        assert cfg.schedule == []
        assert cfg.activation is None
        assert cfg.total_cycles == 0

    def test_total_cycles_from_activation(self) -> None:
        cfg = DeviceConfiguration.model_validate(
            {
                "activation": {
                    "date": "2024-01-01T00:00:00.000",
                    "state": 3,
                    "count": 1000,
                }
            }
        )
        assert cfg.total_cycles == 1000

    def test_unknown_firmware_fields_allowed(self) -> None:
        cfg = DeviceConfiguration.model_validate({"futureField": "value"})
        assert cfg is not None

    def test_binary_elements_aliases(self) -> None:
        be = BinaryElements.model_validate({"EXTRA_WASH": True, "EXTRA_SHAKE": False})
        assert be.extra_wash is True
        assert be.extra_shake is False

    def test_schedule_entry_defaults(self) -> None:
        entry = ScheduleEntry.model_validate({})
        assert entry.day is None
        assert entry.enabled is True

    def test_heater_config(self) -> None:
        h = HeaterConfig.model_validate({"model": 0, "tempOutRef": 161})
        assert h.model == 0
        assert h.temp_out_ref == 161

    def test_water_config(self) -> None:
        w = WaterConfig.model_validate(
            {"fillMax": 125, "fillMin": 30, "senseDetect": 1900, "senseClean": 300}
        )
        assert w.fill_max == 125
        assert w.fill_min == 30


class TestDevice:
    def test_full_payload(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.manufacturer_id == "CGR1234567"
        assert device.name == "Living Room"
        assert device.mac_address == "AABBCCDDEEFF"
        assert device.fw_version == "8.7.203R"

    def test_is_online_connected(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.is_online is True

    def test_is_online_disconnected(self) -> None:
        payload = {**FULL_DEVICE_PAYLOAD, "reportedStatus": "disconnected"}
        device = Device.model_validate(payload)
        assert device.is_online is False

    def test_is_online_case_insensitive(self) -> None:
        payload = {**FULL_DEVICE_PAYLOAD, "reportedStatus": "CONNECTED"}
        device = Device.model_validate(payload)
        assert device.is_online is True

    def test_is_cleaning_false_when_idle(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.is_cleaning is False

    def test_is_cleaning_true_when_running(self) -> None:
        payload = {
            **FULL_DEVICE_PAYLOAD,
            "operationStatus": {"state": 1, "progress": 50},
        }
        device = Device.model_validate(payload)
        assert device.is_cleaning is True

    def test_unique_id_is_manufacturer_id(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.unique_id == "CGR1234567"

    def test_remaining_sani_solution(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.remaining_sani_solution == 39

    def test_last_clean_parsed_as_datetime(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert isinstance(device.last_clean, datetime)

    def test_total_cycles_via_configuration(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.configuration.total_cycles == 600

    def test_update_group(self) -> None:
        device = Device.model_validate(FULL_DEVICE_PAYLOAD)
        assert device.update_group is not None
        assert device.update_group.id == "abc123"
        assert device.update_group.name == "Production World"

    def test_missing_optional_fields_use_defaults(self) -> None:
        minimal = {
            "manufacturerId": "CGR0000001",
            "name": "Test",
            "macAddress": "AABBCCDDEE",
            "hwRevision": "V1",
            "fwVersion": "1.0.0",
        }
        device = Device.model_validate(minimal)
        assert device.is_online is False
        assert device.is_cleaning is False
        assert device.remaining_sani_solution == 0
        assert device.update_group is None

    def test_extra_api_fields_allowed(self) -> None:
        payload = {**FULL_DEVICE_PAYLOAD, "newFieldFromFirmwareUpdate": "value"}
        device = Device.model_validate(payload)
        assert device is not None


class TestNotificationModels:
    def test_notification_list_validates(self) -> None:
        nl = NotificationList.model_validate(NOTIFICATION_PAYLOAD)
        assert nl.user_id == "00000000-0000-0000-0000-000000000001"
        assert len(nl.notifications) == 1

    def test_notification_parsed_data(self) -> None:
        nl = NotificationList.model_validate(NOTIFICATION_PAYLOAD)
        parsed = nl.notifications[0].parsed_data
        assert parsed is not None
        assert parsed.type == 24
        assert parsed.parent_device_id == "CGR1234567"
        assert parsed.version == "8.7.205R"
        assert parsed.device_name == "Living Room"

    def test_notification_empty_data_returns_none(self) -> None:
        n = Notification.model_validate(
            {
                "id": "abc",
                "creationTime": "2026-01-01T00:00:00",
                "data": "",
            }
        )
        assert n.parsed_data is None

    def test_notification_invalid_json_returns_none(self) -> None:
        n = Notification.model_validate(
            {
                "id": "abc",
                "creationTime": "2026-01-01T00:00:00",
                "data": "{not valid json}",
            }
        )
        assert n.parsed_data is None

    def test_empty_notification_list(self) -> None:
        nl = NotificationList.model_validate({"userId": "abc", "notifications": []})
        assert nl.notifications == []


class TestAuthModels:
    def test_login_response(self) -> None:
        resp = LoginResponse.model_validate(
            {
                "userId": "user-123",
                "tenantId": "tenant-456",
                "accountId": "acct-789",
                "accessToken": "jwt.access.token",
                "refreshToken": "jwt.refresh.token",
                "firstName": "Jane",
                "lastName": "Smith",
            }
        )
        assert resp.user_id == "user-123"
        assert resp.access_token == "jwt.access.token"
        assert resp.full_name == "Jane Smith"
        assert resp.email_verified is False

    def test_login_response_full_name_strips_whitespace(self) -> None:
        resp = LoginResponse.model_validate(
            {
                "userId": "u",
                "tenantId": "t",
                "accountId": "a",
                "accessToken": "tok",
                "refreshToken": "ref",
            }
        )
        assert resp.full_name == ""

    def test_refresh_response(self) -> None:
        resp = RefreshResponse.model_validate(
            {
                "token": "new.access.token",
                "refreshToken": "new.refresh.token",
                "expiration": "1800000",  # API returns as string
                "reviewStatus": 0,
                "appVersion": "2.0",
                "enableChat": False,
                "chatUrl": "",
            }
        )
        assert resp.token == "new.access.token"
        assert resp.expiration_ms == 1800000

    def test_api_error(self) -> None:
        err = APIError.model_validate(
            {
                "code": "LOGIN_FAIL",
                "message": "Invalid code",
                "traceId": "trace-abc",
                "hostName": "host1",
                "serviceName": None,
                "data": None,
            }
        )
        assert err.code == "LOGIN_FAIL"
        assert err.message == "Invalid code"
        assert err.service_name is None
