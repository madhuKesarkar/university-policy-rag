"""Password hashing and JWT issuance/verification.

Uses the `bcrypt` library directly rather than passlib's CryptContext: passlib 1.7.4 (latest
release, effectively unmaintained) does version-detection against the bcrypt package that
throws on bcrypt>=4.1's changed internals. Calling bcrypt directly sidesteps that entirely.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings

_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores/rejects input beyond this; enforce it explicitly


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jose.JWTError on an invalid/expired token — callers decide how to respond."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
