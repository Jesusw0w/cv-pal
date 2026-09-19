import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.config import get_settings
from cv_pal.constants import DEFAULT_REFRESH_TOKEN_BYTES
from cv_pal.models import User


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for a subject.

    Args:
        subject: The token subject, i.e. the user's email address.

    Returns:
        The encoded JWT string.
    """
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    claims: dict[str, Any] = {"sub": subject, "exp": expires_at}
    encoded: str = jwt.encode(
        claims,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )
    return encoded


def generate_refresh_token() -> str:
    """Generate an opaque refresh token.

    Returns:
        A URL-safe random string with at least 256 bits of entropy.
    """
    return secrets.token_urlsafe(DEFAULT_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage.

    A refresh token is high-entropy random data, not a guessable secret, so a single
    SHA-256 is appropriate — a password hash's work factor would buy nothing and would
    be paid on every refresh.

    Args:
        token: The plaintext refresh token.

    Returns:
        The hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        The decoded claims if the token is valid, ``None`` if it is expired,
        malformed, or signed with the wrong key.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
    except JWTError:
        return None
    return payload


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by their email address.

    Args:
        db: The async database session.
        email: The email address to search for.

    Returns:
        The ``User`` instance if found, ``None`` otherwise.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
