"""
Unit tests for authentication service.
"""

from datetime import timedelta

from app.services.auth import (
    create_access_token,
    create_refresh_token_jwt,
    decode_token,
    generate_jti,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_hash_password(self):
        """Password is hashed."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        # argon2 hashes start with $argon2
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        """Correct password verifies."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password fails."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Same password produces different hashes (salted)."""
        password = "securepassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2
        # But both verify correctly
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWTTokens:
    """Tests for JWT token operations."""

    def test_create_access_token(self):
        """Access token is created."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data)

        assert token is not None
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert len(token.split(".")) == 3
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"
        assert "jti" in payload

    def test_create_refresh_token_jwt(self):
        """Refresh token is created."""
        data = {"sub": "user-123"}
        jti = generate_jti()
        token = create_refresh_token_jwt(data, jti=jti)

        assert token is not None
        assert len(token) > 0
        assert len(token.split(".")) == 3

    def test_decode_access_token(self):
        """Access token decodes correctly."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data)

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "jti" in payload

    def test_decode_refresh_token(self):
        """Refresh token decodes correctly."""
        data = {"sub": "user-123"}
        jti = generate_jti()
        token = create_refresh_token_jwt(data, jti=jti)

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_decode_invalid_token(self):
        """Invalid token returns None."""
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_tampered_token(self):
        """Tampered token returns None."""
        token = create_access_token({"sub": "user-123"})
        # Tamper with the token
        tampered = token[:-5] + "xxxxx"

        payload = decode_token(tampered)
        assert payload is None

    def test_token_expiration(self):
        """Token with past expiration is invalid."""
        data = {"sub": "user-123"}
        # Create token that expired 1 hour ago
        token = create_access_token(data, expires_delta=timedelta(hours=-1))

        payload = decode_token(token)
        assert payload is None


class TestTokenTypes:
    """Tests for token type validation."""

    def test_access_token_type(self):
        """Access token has type 'access'."""
        token = create_access_token({"sub": "123"})
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        """Refresh token has type 'refresh'."""
        token = create_refresh_token_jwt({"sub": "123"}, jti=generate_jti())
        payload = decode_token(token)
        assert payload["type"] == "refresh"
