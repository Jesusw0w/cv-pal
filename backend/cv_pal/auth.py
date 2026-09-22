import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.config import get_settings
from cv_pal.constants import (
    DEFAULT_ACCESS_COOKIE,
    DEFAULT_REFRESH_COOKIE,
    DEFAULT_REFRESH_TOKEN_BYTES,
    DEFAULT_SESSION_HEADER,
    DEFAULT_TOKEN_TYPE_COOKIE,
)
from cv_pal.models import User


def create_access_token(subject: str, *, version: int) -> str:
    """Create a signed JWT access token for a subject.

    Args:
        subject: The token subject, i.e. the user's email address.
        version: The user's current token version; the token dies when it changes.

    Returns:
        The encoded JWT string.
    """
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    claims: dict[str, Any] = {"sub": subject, "ver": version, "exp": expires_at}
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
    except jwt.PyJWTError:
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


def wants_cookie_session(request: Request) -> bool:
    """Report whether the client asked for an HttpOnly cookie session.

    Args:
        request: The incoming request.

    Returns:
        True when the session header names cookie mode.
    """
    return request.headers.get(DEFAULT_SESSION_HEADER) == DEFAULT_TOKEN_TYPE_COOKIE


def set_session_cookies(response: Response, *, access: str, refresh: str) -> None:
    """Put a token pair into HttpOnly cookies.

    Args:
        response: The response to attach the cookies to.
        access: The access token.
        refresh: The refresh token.
    """
    settings = get_settings()
    for name, value, max_age in (
        (DEFAULT_ACCESS_COOKIE, access, settings.access_token_expire_minutes * 60),
        (DEFAULT_REFRESH_COOKIE, refresh, settings.refresh_token_expire_days * 86400),
    ):
        response.set_cookie(
            name,
            value,
            max_age=max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
        )


def clear_session_cookies(response: Response) -> None:
    """Remove both session cookies.

    Args:
        response: The response to clear the cookies on.
    """
    settings = get_settings()
    for name in (DEFAULT_ACCESS_COOKIE, DEFAULT_REFRESH_COOKIE):
        response.delete_cookie(
            name, httponly=True, secure=settings.cookie_secure, samesite="strict"
        )
