"""
Unit tests for CSRF protection middleware.

Tests the double-submit cookie CSRF protection implementation.
"""

import pytest

from app.middleware.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRF_TOKEN_LENGTH,
    generate_csrf_token,
    get_csrf_cookie_settings,
)


class TestCsrfTokenGeneration:
    """Tests for CSRF token generation."""

    def test_generate_csrf_token_length(self):
        """Token should have sufficient entropy (32 bytes = 256 bits)."""
        token = generate_csrf_token()
        # URL-safe base64 encoding: 32 bytes -> ~43 characters
        assert len(token) >= 40

    def test_generate_csrf_token_uniqueness(self):
        """Each token should be unique."""
        tokens = [generate_csrf_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generate_csrf_token_url_safe(self):
        """Token should be URL-safe (no special characters that need encoding)."""
        token = generate_csrf_token()
        # URL-safe base64 uses only alphanumeric, -, and _
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in allowed_chars for c in token)


class TestCsrfCookieSettings:
    """Tests for CSRF cookie configuration."""

    def test_cookie_settings_httponly_false(self):
        """httpOnly must be False so JS can read the token."""
        settings = get_csrf_cookie_settings()
        assert settings["httponly"] is False

    def test_cookie_settings_samesite_lax(self):
        """SameSite should be Lax for additional protection."""
        settings = get_csrf_cookie_settings()
        assert settings["samesite"] == "lax"

    def test_cookie_settings_path_root(self):
        """Path should be / so cookie is available to all endpoints."""
        settings = get_csrf_cookie_settings()
        assert settings["path"] == "/"

    def test_cookie_settings_key(self):
        """Cookie key should match constant."""
        settings = get_csrf_cookie_settings()
        assert settings["key"] == CSRF_COOKIE_NAME


class TestCsrfConstants:
    """Tests for CSRF constants."""

    def test_cookie_name(self):
        """Cookie name should be csrf_token."""
        assert CSRF_COOKIE_NAME == "csrf_token"

    def test_header_name(self):
        """Header name should be X-CSRF-Token."""
        assert CSRF_HEADER_NAME == "X-CSRF-Token"

    def test_token_length(self):
        """Token length should be 32 bytes (256 bits of entropy)."""
        assert CSRF_TOKEN_LENGTH == 32


