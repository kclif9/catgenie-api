"""Request signing for the CatGenie API.

Every request to iot.petnovations.com requires 4 signature headers derived from:
- An 84-character per-account secret (stored after login)
- Static AES key and derivation parameters baked into the React Native bundle
- The request path, body, query params, and current timestamp

Reverse-engineered from the CatGenie React Native app.
Reference: https://github.com/Rukongai/CatDjinni/blob/master/research/App/SIGNATURE_ALGORITHM.md
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import random
import time
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# Environment-specific derivation parameters: "index-prefix-suffix"
# The HMAC key is built as: prefix + secret[index:index+28] + suffix (always 32 chars)
DERIVATION_PARAMS: dict[str, str] = {
    "dev": "0-1b-Mg",
    "staging": "28-wq-0C",
    "production": "56-Yt-x3",
}

# Static AES key for x-pm-en-dec header encryption.
# Constructed from: "P-3Rp6d81Kw9a3Z-" + getMessage("vyC") where
#   getMessage = (I) => ("eiRXW0HW" + I).split('').reverse().join('') + "yITk6"
#   getMessage("vyC") => "CyvWH0WXRieyITk6"
AES_KEY = b"P-3Rp6d81Kw9a3Z-CyvWH0WXRieyITk6"  # 32 bytes


def derive_hmac_key(secret: str, environment: str = "production") -> str:
    """Derive the 32-character HMAC signing key from the 84-char account secret."""
    params = DERIVATION_PARAMS.get(environment, DERIVATION_PARAMS["production"])
    parts = params.split("-")
    index = int(parts[0])
    prefix = parts[1]
    suffix = parts[2]
    extracted = secret[index : index + 28]
    return prefix + extracted + suffix


def serialize_data(data: dict[str, Any] | None) -> str:
    """Serialize request data for HMAC signing.

    Keys are sorted in REVERSE alphabetical order, values are concatenated,
    spaces stripped, and the result lowercased. Keys with None values and
    'imageContent' are skipped.
    """
    if not data:
        return ""
    sorted_keys = sorted(data.keys(), reverse=True)
    result = ""
    for key in sorted_keys:
        value = data.get(key)
        if value is not None and key != "imageContent":
            result += str(value)
    return result.replace(" ", "").lower()


def _hmac_sha256(key: str, message: str) -> str:
    """HMAC-SHA256, returned as lowercase hex."""
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _random_string(length: int) -> str:
    # App charset: digits + uppercase (with T duplicated, Y missing) + lowercase (j missing)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXTZabcdefghiklmnopqrstuvwxyz"
    return "".join(random.choice(chars) for _ in range(length))  # noqa: S311


def _insert_char(s: str, char: str) -> str:
    pos = random.randint(0, len(s))  # noqa: S311
    return s[:pos] + char + s[pos:]


def encrypt_str1(country_code: int, phone: str) -> str:
    """Encrypt phone number for the str1 body field.

    Format: +{countryCode}{phone}-{7_random_chars_with_X_inserted}
    Encrypted with AES-CBC, static key, zero IV.
    """
    random_suffix = _insert_char(_random_string(7), "X")
    plaintext = f"+{country_code}{phone}-{random_suffix}"
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b"\x00" * 16)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def render_t_path(path: str) -> str:
    """Get the path component for x-render-t.

    The facade/v1/ prefix is stripped; all other paths are used as-is.
    """
    clean = path.lstrip("/")
    if clean.startswith("facade/v1/"):
        clean = clean[len("facade/v1/") :]
    return clean


def generate_enc_dec(timestamp_ms: int) -> str:
    """Generate the x-pm-en-dec header (AES-CBC encrypted timestamp).

    Algorithm:
    1. If (timestamp/100) is odd, add 100
    2. Build plaintext: "{adjusted_timestamp}-{random_7_chars_with_Z_inserted}"
    3. AES-CBC encrypt with static key and zero IV
    4. Base64 encode
    """
    ts = timestamp_ms
    if (ts // 100) % 2 != 0:
        ts += 100

    random_part = _insert_char(_random_string(7), "Z")
    plaintext = f"{ts}-{random_part}"

    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b"\x00" * 16)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def generate_request_headers(
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    secret: str = "",
    environment: str = "production",
) -> dict[str, str]:
    """Generate all required signature headers for a CatGenie API request.

    Returns a dict with:
    - x-pm-en-dec: AES-encrypted timestamp
    - x-pm-en-ver: "1.0.0"
    - x-render-t: "{path}/{timestamp_ms}"
    - y-pm-sg-b: HMAC-SHA256 body signature
    - y-pm-sg-p: HMAC-SHA256 params signature
    """
    timestamp_ms = int(time.time() * 1000)

    rt_path = render_t_path(path)
    render_t = f"{rt_path}/{timestamp_ms}"

    headers: dict[str, str] = {
        "x-pm-en-dec": generate_enc_dec(timestamp_ms),
        "x-pm-en-ver": "1.0.0",
        "x-render-t": render_t,
    }

    # HMAC signatures — computed when a signing secret is available.
    if secret:
        hmac_key = derive_hmac_key(secret, environment)

        body_data = ""
        if method.upper() in ("POST", "PUT", "PATCH") and body:
            body_data = serialize_data(body)
        body_data += render_t

        params_data = ""
        if params:
            params_data = serialize_data(params)
        params_data += render_t

        headers["y-pm-sg-b"] = _hmac_sha256(hmac_key, body_data)
        headers["y-pm-sg-p"] = _hmac_sha256(hmac_key, params_data)

    return headers
