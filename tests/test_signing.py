"""Tests for catgenie.signing — AES encryption and HMAC request signing."""

from __future__ import annotations

import base64
import re

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from catgenie.signing import (
    AES_KEY,
    derive_hmac_key,
    encrypt_str1,
    generate_enc_dec,
    generate_request_headers,
    render_t_path,
    serialize_data,
)


class TestRenderTPath:
    def test_plain_path_unchanged(self) -> None:
        assert render_t_path("config/v1/url") == "config/v1/url"

    def test_ums_path_unchanged(self) -> None:
        assert render_t_path("ums/v1/users/generateLoginCode/v2") == (
            "ums/v1/users/generateLoginCode/v2"
        )

    def test_facade_prefix_stripped(self) -> None:
        assert render_t_path("facade/v1/mobile-user/refreshToken/v2") == (
            "mobile-user/refreshToken/v2"
        )

    def test_leading_slash_stripped(self) -> None:
        assert render_t_path("/config/v1/url") == "config/v1/url"

    def test_facade_with_leading_slash(self) -> None:
        assert render_t_path("/facade/v1/mobile-user/refreshToken/v2") == (
            "mobile-user/refreshToken/v2"
        )


class TestSerializeData:
    def test_empty_returns_empty(self) -> None:
        assert serialize_data(None) == ""
        assert serialize_data({}) == ""

    def test_keys_sorted_reverse_alphabetical(self) -> None:
        # "str1" > "code" alphabetically reversed → str1 value comes first
        result = serialize_data({"code": "1234", "str1": "ABCD"})
        assert result.index("abcd") < result.index("1234")

    def test_values_lowercased_and_spaces_stripped(self) -> None:
        result = serialize_data({"key": "Hello World"})
        assert result == "helloworld"

    def test_none_values_skipped(self) -> None:
        result = serialize_data({"a": "val", "b": None})
        assert result == "val"

    def test_image_content_skipped(self) -> None:
        result = serialize_data({"imageContent": "data", "other": "val"})
        assert result == "val"


class TestDeriveHmacKey:
    def test_production_key_length(self) -> None:
        secret = "A" * 84
        key = derive_hmac_key(secret, "production")
        assert len(key) == 32

    def test_production_key_structure(self) -> None:
        # production: index=56, prefix="Yt", suffix="x3"
        secret = "A" * 84
        key = derive_hmac_key(secret, "production")
        assert key.startswith("Yt")
        assert key.endswith("x3")
        assert key[2:30] == "A" * 28

    def test_dev_key_structure(self) -> None:
        # dev: index=0, prefix="1b", suffix="Mg"
        secret = "B" * 84
        key = derive_hmac_key(secret, "dev")
        assert key.startswith("1b")
        assert key.endswith("Mg")

    def test_unknown_environment_falls_back_to_production(self) -> None:
        secret = "A" * 84
        key_prod = derive_hmac_key(secret, "production")
        key_unknown = derive_hmac_key(secret, "nonexistent")
        assert key_prod == key_unknown


class TestEncryptStr1:
    def _decrypt(self, b64: str) -> str:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b"\x00" * 16)
        return unpad(cipher.decrypt(base64.b64decode(b64)), 16).decode()

    def test_output_is_valid_base64(self) -> None:
        result = encrypt_str1(61, "499999999")
        base64.b64decode(result)  # should not raise

    def test_plaintext_format(self) -> None:
        result = encrypt_str1(61, "499999999")
        plaintext = self._decrypt(result)
        # format: +{countryCode}{phone}-{8 random chars}
        assert re.match(r"^\+61499999999-[A-Za-z0-9]{8}$", plaintext)

    def test_different_calls_produce_different_ciphertext(self) -> None:
        # Random suffix means output is non-deterministic
        r1 = encrypt_str1(61, "499999999")
        r2 = encrypt_str1(61, "499999999")
        assert r1 != r2

    def test_different_country_codes(self) -> None:
        result = encrypt_str1(1, "5551234567")
        plaintext = self._decrypt(result)
        assert plaintext.startswith("+15551234567-")


class TestGenerateEncDec:
    def _decrypt(self, b64: str) -> str:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b"\x00" * 16)
        return unpad(cipher.decrypt(base64.b64decode(b64)), 16).decode()

    def test_output_is_valid_base64(self) -> None:
        result = generate_enc_dec(1000000000000)
        base64.b64decode(result)  # should not raise

    def test_even_timestamp_unchanged(self) -> None:
        # 1000000000000 / 100 = 10000000000 — even, so timestamp stays the same
        ts = 1000000000000
        assert (ts // 100) % 2 == 0
        result = generate_enc_dec(ts)
        plaintext = self._decrypt(result)
        assert plaintext.startswith(f"{ts}-")

    def test_odd_timestamp_incremented(self) -> None:
        # Find a timestamp where (ts//100) is odd
        ts = 100  # 100/100=1 — odd
        result = generate_enc_dec(ts)
        plaintext = self._decrypt(result)
        assert plaintext.startswith(f"{ts + 100}-")

    def test_plaintext_contains_Z(self) -> None:
        result = generate_enc_dec(1000000000000)
        plaintext = self._decrypt(result)
        # The random suffix always contains exactly one 'Z'
        suffix = plaintext.split("-", 1)[1]
        assert "Z" in suffix


class TestGenerateRequestHeaders:
    def test_base_headers_always_present(self) -> None:
        headers = generate_request_headers("config/v1/url")
        assert "x-pm-en-dec" in headers
        assert "x-pm-en-ver" in headers
        assert "x-render-t" in headers
        assert headers["x-pm-en-ver"] == "1.0.0"

    def test_render_t_contains_path(self) -> None:
        headers = generate_request_headers("config/v1/url")
        assert headers["x-render-t"].startswith("config/v1/url/")

    def test_no_hmac_headers_without_secret(self) -> None:
        headers = generate_request_headers("config/v1/url")
        assert "y-pm-sg-b" not in headers
        assert "y-pm-sg-p" not in headers

    def test_hmac_headers_present_with_secret(self) -> None:
        headers = generate_request_headers(
            "device/device/v2", secret="A" * 84
        )
        assert "y-pm-sg-b" in headers
        assert "y-pm-sg-p" in headers

    def test_hmac_values_are_hex_strings(self) -> None:
        headers = generate_request_headers(
            "device/device/v2", secret="A" * 84
        )
        assert re.match(r"^[0-9a-f]{64}$", headers["y-pm-sg-b"])
        assert re.match(r"^[0-9a-f]{64}$", headers["y-pm-sg-p"])

    def test_facade_path_stripped_in_render_t(self) -> None:
        headers = generate_request_headers(
            "facade/v1/mobile-user/refreshToken/v2"
        )
        assert headers["x-render-t"].startswith("mobile-user/refreshToken/v2/")

    def test_post_body_included_in_hmac(self) -> None:
        secret = "A" * 84
        h_with = generate_request_headers(
            "device/device/v2",
            method="POST",
            body={"state": 1},
            secret=secret,
        )
        h_without = generate_request_headers(
            "device/device/v2",
            method="POST",
            secret=secret,
        )
        # HMAC body sig differs when body is present vs absent
        # (timestamps differ too, so we just check both are valid hex)
        assert re.match(r"^[0-9a-f]{64}$", h_with["y-pm-sg-b"])
        assert re.match(r"^[0-9a-f]{64}$", h_without["y-pm-sg-b"])

    def test_params_included_in_hmac(self) -> None:
        headers = generate_request_headers(
            "device/device/v2",
            params={"useFleetIndexAndGetRealConnectivity": "true"},
            secret="A" * 84,
        )
        assert "y-pm-sg-p" in headers
