import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.auth import (
    create_access_token,
    generate_refresh_token,
    get_user_by_email,
    hash_refresh_token,
)
from cv_pal.config import get_settings
from cv_pal.exceptions import InvalidRefreshTokenError
from cv_pal.hashing import hash_password, needs_rehash, verify_password
from cv_pal.models import RefreshToken, User
from cv_pal.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


def _lockout_key(email: str) -> str:
    """Build the failure-tracking key for a submitted email.

    Args:
        email: The email address as submitted.

    Returns:
        A normalised key.
    """
    return f"login:{email.strip().casefold()}"


async def authenticate(
    db: AsyncSession, *, email: str, password: str, limiter: RateLimiter
) -> User | None:
    """Authenticate a user, applying failure backoff and upgrading legacy hashes.

    Failures are counted against the submitted email whether or not an account exists,
    so the backoff cannot be used to discover which addresses are registered.

    Args:
        db: Async database session.
        email: The submitted email address.
        password: The submitted password.
        limiter: Failure-backoff tracker.

    Returns:
        The authenticated user, or ``None`` if the credentials do not match.

    Raises:
        RateLimitedError: If this account is currently in failure backoff.
    """
    key = _lockout_key(email)
    limiter.check_locked(key)

    user = await get_user_by_email(db, email)

    if user is None:
        # Hash anyway so a missing account is not measurably faster than a wrong
        # password, which would otherwise reveal which addresses exist.
        hash_password(password)
        limiter.record_failure(key)
        return None

    if not verify_password(password, user.hashed_password):
        limiter.record_failure(key)
        return None

    limiter.reset(key)

    if needs_rehash(user.hashed_password):
        # The plaintext is only available here, so this is the one chance to upgrade.
        user.hashed_password = hash_password(password)
        await db.commit()
        await db.refresh(user)
        logger.info("Upgraded password hash for user %s", user.id)

    return user


async def issue_tokens(db: AsyncSession, *, user: User) -> tuple[str, str]:
    """Issue an access token and a fresh refresh token for a user.

    Returns:
        A tuple of ``(access_token, refresh_token)``. The refresh token is returned in
        plaintext exactly once; only its hash is stored.
    """
    settings = get_settings()
    refresh_token = generate_refresh_token()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()

    return create_access_token(user.email), refresh_token


async def _find_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    """Look up a refresh token by its hash.

    Args:
        db: Async database session.
        token: The plaintext refresh token.

    Returns:
        The stored record, or ``None`` if no such token exists.
    """
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    return result.scalar_one_or_none()


async def _revoke_all_for_user(db: AsyncSession, user_id: int) -> None:
    """Revoke every unrevoked refresh token belonging to a user.

    Args:
        db: Async database session.
        user_id: The user whose sessions should end.
    """
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def rotate_refresh_token(db: AsyncSession, *, token: str) -> tuple[str, str]:
    """Exchange a refresh token for a new token pair.

    The presented token is revoked and replaced, so each refresh token is usable once.
    Presenting an already-revoked token is treated as evidence that a token has been
    stolen — the legitimate holder and the thief cannot both have used it — so every
    session for that user is revoked and re-authentication is required.

    Args:
        db: Async database session.
        token: The plaintext refresh token presented by the client.

    Returns:
        A tuple of ``(access_token, refresh_token)``.

    Raises:
        InvalidRefreshTokenError: If the token is unknown, expired, revoked, or belongs
            to an inactive account.
    """
    stored = await _find_refresh_token(db, token)
    if stored is None:
        raise InvalidRefreshTokenError

    if stored.revoked_at is not None:
        logger.warning(
            "Refresh token reuse detected for user %s; revoking all sessions",
            stored.user_id,
        )
        await _revoke_all_for_user(db, stored.user_id)
        await db.commit()
        raise InvalidRefreshTokenError

    # Stored timestamps come back naive on SQLite, so compare in a single convention.
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise InvalidRefreshTokenError

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError

    stored.revoked_at = datetime.now(UTC)
    return await issue_tokens(db, user=user)


async def revoke_refresh_token(db: AsyncSession, *, token: str) -> None:
    """Revoke a single refresh token, ending that session.

    Logging out an unknown or already-revoked token is not an error: the caller's intent
    is satisfied either way, and reporting the difference would confirm which tokens
    exist.

    Args:
        db: Async database session.
        token: The plaintext refresh token to revoke.
    """
    stored = await _find_refresh_token(db, token)
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
    await db.commit()


async def revoke_all_sessions(db: AsyncSession, *, user_id: int) -> None:
    """Revoke every refresh token for a user, logging out all their devices.

    Args:
        db: Async database session.
        user_id: The user whose sessions should end.
    """
    await _revoke_all_for_user(db, user_id)
    await db.commit()
