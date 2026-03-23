from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt
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


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "token_type": "access",
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
