"""Shared fixtures for the CatGenie test suite."""

from __future__ import annotations


FULL_DEVICE_PAYLOAD: dict = {
    "manufacturerId": "CGR1234567",
    "name": "Living Room",
    "macAddress": "AABBCCDDEEFF",
    "hwRevision": "V1",
    "fwVersion": "8.7.203R",
    "type": 0,
    "status": 2,
    "reportedStatus": "connected",
    "pumpTypeEnum": "PEGASUS",
    "connectionMode": "WIFI",
    "lastClean": "2025-05-01T01:01:01",
    "remainingSaniSolution": 39,
    "serviceLevel": "Deluxe",
    "countryCode": 1,
    "lowHeater": True,
    "fanShutter": True,
    "dome": False,
    "configuration": {
        "childLock": 0,
        "autoLock": 0,
        "volumeLevel": 7,
        "mode": 0,
        "catSense": 16,
        "timezone": "+00:00",
        "catDelay": 600,
        "pumpPctT": 100,
        "extraDry": False,
        "schedule": [],
        "activation": {
            "date": "2024-01-01T01:01:01.000",
            "state": 3,
            "count": 600,
        },
        "heater": {"model": 0, "tempOutRef": 161},
        "water": {
            "fillMax": 125,
            "fillMin": 30,
            "senseDetect": 1900,
            "senseClean": 300,
        },
        "binaryElements": {"EXTRA_WASH": False, "EXTRA_SHAKE": False},
    },
    "operationStatus": {"state": 0, "progress": 255},
    "activeErrors": [],
    "updateGroup": {"id": "abc123", "name": "Production World"},
}

NOTIFICATION_PAYLOAD: dict = {
    "userId": "00000000-0000-0000-0000-000000000001",
    "notifications": [
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "creationTime": "2026-01-01T00:00:00.000",
            "data": (
                '{"errorType":"","parentDeviceId":"CGR1234567","type":24,'
                '"version":"8.7.205R","deviceName":"Living Room",'
                '"deviceId":"AABBCCDDEEFF",'
                '"eventTimestamp":"2026-01-01T00:00:00.000"}'
            ),
        }
    ],
}

# 84-character secret matching the production derivation params
FAKE_SECRET = "A" * 84
