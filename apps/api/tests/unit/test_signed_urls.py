"""
Unit tests for signed URL service.

Tests:
- Token generation
- Token validation
- Token expiry
- Invalid token handling
- Tamper detection
"""

import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.signed_urls import (
    SignedUrlError,
    SignedUrlService,
    generate_signed_url,
    validate_signed_url,
)


class TestSignedUrlService:
    """Tests for SignedUrlService class."""

    def test_generate_token_format(self):
        """Token should be in format 'expires.signature'."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, expires = service.generate_token(asset_id)

        # Check format
        parts = token.split(".")
        assert len(parts) == 2, "Token should have two parts separated by dot"

        # First part should be the expiry timestamp
        assert parts[0] == str(expires)

        # Second part should be the signature (32 hex chars)
        assert len(parts[1]) == 32
        assert all(c in "0123456789abcdef" for c in parts[1])

    def test_generate_token_default_ttl(self):
        """Default TTL should be 300 seconds."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, expires = service.generate_token(asset_id)

        # Expires should be ~300 seconds in the future
        now = int(time.time())
        assert 299 <= expires - now <= 301

    def test_generate_token_custom_ttl(self):
        """Custom TTL should be respected."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, expires = service.generate_token(asset_id, ttl_seconds=600)

        # Expires should be ~600 seconds in the future
        now = int(time.time())
        assert 599 <= expires - now <= 601

    def test_validate_token_success(self):
        """Valid token should pass validation."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, _ = service.generate_token(asset_id)

        # Should not raise
        assert service.validate_token(asset_id, token) is True

    def test_validate_token_wrong_asset_id(self):
        """Token for different asset should fail."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id_1 = uuid4()
        asset_id_2 = uuid4()

        token, _ = service.generate_token(asset_id_1)

        # Should raise for different asset
        with pytest.raises(SignedUrlError, match="Invalid signature"):
            service.validate_token(asset_id_2, token)

    def test_validate_token_expired(self):
        """Expired token should fail."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        # Generate token with very short TTL
        token, _ = service.generate_token(asset_id, ttl_seconds=1)

        # Wait for expiry
        time.sleep(1.5)

        # Should raise
        with pytest.raises(SignedUrlError, match="Token expired"):
            service.validate_token(asset_id, token)

    def test_validate_token_tampered_signature(self):
        """Tampered signature should fail."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, _ = service.generate_token(asset_id)

        # Tamper with signature
        parts = token.split(".")
        tampered_token = f"{parts[0]}.{'a' * 32}"

        with pytest.raises(SignedUrlError, match="Invalid signature"):
            service.validate_token(asset_id, tampered_token)

    def test_validate_token_tampered_expiry(self):
        """Tampered expiry should fail (signature mismatch)."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        token, expires = service.generate_token(asset_id)

        # Tamper with expiry to extend it
        parts = token.split(".")
        new_expiry = expires + 3600  # Add 1 hour
        tampered_token = f"{new_expiry}.{parts[1]}"

        with pytest.raises(SignedUrlError, match="Invalid signature"):
            service.validate_token(asset_id, tampered_token)

    def test_validate_token_invalid_format(self):
        """Invalid token format should fail."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        # No dot separator
        with pytest.raises(SignedUrlError, match="Invalid token format"):
            service.validate_token(asset_id, "no-dot-separator")

        # Multiple dots
        with pytest.raises(SignedUrlError, match="Invalid token format"):
            service.validate_token(asset_id, "too.many.dots")

        # Non-numeric expiry
        with pytest.raises(SignedUrlError, match="Invalid token"):
            service.validate_token(asset_id, "notanumber.abc123")

    def test_different_secrets_produce_different_signatures(self):
        """Different secret keys should produce different tokens."""
        asset_id = uuid4()

        service1 = SignedUrlService(secret_key="secret-1")
        service2 = SignedUrlService(secret_key="secret-2")

        token1, _ = service1.generate_token(asset_id)
        token2, _ = service2.generate_token(asset_id)

        # Extract signatures
        sig1 = token1.split(".")[1]
        sig2 = token2.split(".")[1]

        assert sig1 != sig2

    def test_token_from_different_secret_fails(self):
        """Token generated with different secret should fail validation."""
        asset_id = uuid4()

        service1 = SignedUrlService(secret_key="secret-1")
        service2 = SignedUrlService(secret_key="secret-2")

        token, _ = service1.generate_token(asset_id)

        with pytest.raises(SignedUrlError, match="Invalid signature"):
            service2.validate_token(asset_id, token)

    def test_generate_url(self):
        """generate_url should return full URL with token."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        url, expires = service.generate_url(asset_id)

        assert url.startswith(f"/api/v1/assets/{asset_id}/file?token=")
        assert str(expires) in url

    def test_generate_url_custom_base_path(self):
        """Custom base path should be used."""
        service = SignedUrlService(secret_key="test-secret")
        asset_id = uuid4()

        url, _ = service.generate_url(asset_id, base_path="/custom/path")

        assert url.startswith(f"/custom/path/{asset_id}/file?token=")


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_generate_signed_url(self):
        """generate_signed_url should work with default service."""
        asset_id = uuid4()

        url, expires = generate_signed_url(asset_id)

        assert f"/assets/{asset_id}/file?token=" in url
        assert expires > int(time.time())

    def test_validate_signed_url(self):
        """validate_signed_url should validate tokens from generate_signed_url."""
        asset_id = uuid4()

        url, _ = generate_signed_url(asset_id)

        # Extract token from URL
        token = url.split("token=")[1]

        # Should not raise
        assert validate_signed_url(asset_id, token) is True

    def test_validate_signed_url_cross_company_prevention(self):
        """Different asset_id should fail validation (prevents cross-company access)."""
        asset_id_a = uuid4()
        asset_id_b = uuid4()

        url_a, _ = generate_signed_url(asset_id_a)
        token_a = url_a.split("token=")[1]

        # Token for asset A should not work for asset B
        with pytest.raises(SignedUrlError, match="Invalid signature"):
            validate_signed_url(asset_id_b, token_a)


