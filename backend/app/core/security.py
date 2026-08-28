"""Password hashing, JWT issue/verify, and Fernet encryption for stored provider API keys.

Access/refresh tokens are plain JSON returned to the Next.js BFF, which is the only
client and is responsible for turning them into httpOnly cookies — FastAPI never sets
cookies itself (see frontend/DESIGN.md §5).
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
_fernet = Fernet(settings.fernet_key.encode())

# bcrypt ignores any bytes past the 72nd, and raises on newer versions if the input is
# longer — truncate explicitly so a long passphrase never hashes to the same value as
# its first-72-bytes prefix without noise, and never crashes the request.
_BCRYPT_MAX_BYTES = 72


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    truncated = password.encode()[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode()[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, hashed.encode())


def _create_token(subject: UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days)
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidTokenError("Token is invalid or expired") from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"Expected a {expected_type.value} token")

    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Token subject is malformed") from exc


# --- Provider API key encryption at rest ---
# FERNET_KEY must be generated once per deployment (Fernet.generate_key()) and never
# committed. Decrypted keys live only in-memory for the duration of a single provider
# call; there is no code path that returns a decrypted key to a client.


def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored API key could not be decrypted — FERNET_KEY may have changed") from exc


def mask_secret(plaintext: str, keep: int = 4) -> str:
    """e.g. 'sk-abcdef123456' -> 'sk-a...3456' — never send the real key back to a client."""
    if len(plaintext) <= keep * 2:
        return "*" * len(plaintext)
    return f"{plaintext[:keep]}...{plaintext[-keep:]}"
