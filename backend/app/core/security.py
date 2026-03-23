from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AppError

class JWTPayload(BaseModel):
    sub: int
    email: str
    token_type: str = "access"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _normalize_base32(secret: str) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return f"{secret}{padding}"


def _totp_counter(for_time: datetime | None = None, period_seconds: int = 30) -> int:
    instant = for_time or datetime.now(timezone.utc)
    return int(instant.timestamp() // period_seconds)


def generate_totp_code(
    secret: str,
    *,
    for_time: datetime | None = None,
    period_seconds: int = 30,
    digits: int = 6,
) -> str:
    key = base64.b32decode(_normalize_base32(secret), casefold=True)
    counter = _totp_counter(for_time, period_seconds).to_bytes(8, "big")
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return str(binary % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    normalized = code.strip()
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    now = datetime.now(timezone.utc)
    for delta in range(-window, window + 1):
        candidate = generate_totp_code(
            secret,
            for_time=now + timedelta(seconds=delta * 30),
        )
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def build_totp_uri(secret: str, *, email: str, issuer: str = "ESGvist") -> str:
    account_name = email.replace(":", "%3A")
    issuer_name = issuer.replace(" ", "%20")
    return (
        f"otpauth://totp/{issuer_name}:{account_name}"
        f"?secret={secret}&issuer={issuer_name}&algorithm=SHA1&digits=6&period=30"
    )


def generate_backup_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]


def hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_backup_code(code: str, hashed_codes: list[str] | None) -> tuple[bool, list[str]]:
    remaining = list(hashed_codes or [])
    candidate = hash_backup_code(code.strip().lower())
    for idx, hashed in enumerate(remaining):
        if hmac.compare_digest(candidate, hashed):
            del remaining[idx]
            return True, remaining
    return False, list(hashed_codes or [])


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "token_type": "access",
        "jti": secrets.token_urlsafe(12),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {
        "sub": str(user_id),
        "email": email,
        "token_type": "refresh",
        "jti": secrets.token_urlsafe(12),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> JWTPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return JWTPayload(
            sub=int(payload["sub"]),
            email=payload["email"],
            token_type=payload.get("token_type", "access"),
        )
    except (JWTError, KeyError, ValueError):
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid or expired token")
