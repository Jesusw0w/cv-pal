"""Personal access tokens: how an external agent signs in to the MCP endpoint.

A token is a long-lived credential handed to software the user does not control, so it
is narrower than a session in every direction: scoped, always expiring, usable only on
the MCP endpoint, capped in number, and revoked by a password change. Creating one needs
the account's password, for the same reason changing the password does.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.auth import hash_refresh_token
from cv_pal.constants import (
    DEFAULT_API_TOKEN_BYTES,
    DEFAULT_API_TOKEN_DISPLAY_CHARS,
    DEFAULT_API_TOKEN_MAX_PER_USER,
    DEFAULT_API_TOKEN_PREFIX,
    DEFAULT_API_TOKEN_TOUCH_SECONDS,
    DEFAULT_ERROR_API_TOKEN_LIMIT,
    DEFAULT_ERROR_API_TOKEN_NOT_FOUND,
    DEFAULT_ERROR_WRONG_PASSWORD,
    SCOPE_PROFILE,
    SCOPE_READ,
    SCOPE_WRITE,
)
from cv_pal.exceptions import AuthenticationError, ConflictError, NotFoundError
from cv_pal.hashing import verify_password
from cv_pal.models import ApiToken, User


@dataclass(frozen=True, slots=True)
class ResolvedToken:
    """A token that checked out, and whose it is."""

    token_id: int
    user: User
    scopes: tuple[str, ...]
    expires_at: datetime


def _aware(moment: datetime) -> datetime:
    """Read a stored timestamp as UTC; SQLite hands them back naive.

    Args:
        moment: A timestamp from the database.

    Returns:
        The same instant, timezone-aware.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _live(now: datetime) -> ColumnElement[bool]:
    """Build the condition for a token that can still be used.

    Args:
        now: The current time.

    Returns:
        The filter clause.
    """
    return ApiToken.revoked_at.is_(None) & (ApiToken.expires_at > now)


async def list_tokens(db: AsyncSession, *, user_id: int) -> list[ApiToken]:
    """Return the user's tokens that have not been revoked, newest first.

    Expired ones are kept in the list so the user can see why an agent stopped working.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The tokens.
    """
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
        .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    )
    return list(result.scalars().all())


async def create_token(
    db: AsyncSession,
    *,
    user: User,
    password: str,
    name: str,
    write: bool,
    expires_in_days: int,
    edit_profile: bool = False,
) -> tuple[ApiToken, str]:
    """Issue a token. The plaintext is returned here and never again.

    Args:
        db: Async database session.
        user: The authenticated account.
        password: The account's password, as proof the holder is present.
        name: What the user calls it, e.g. the agent it is for.
        write: Whether it may record postings and applications, not only read.
        expires_in_days: How long it lives.
        edit_profile: Whether it may change the career profile and goals.

    Returns:
        The stored token and its plaintext.

    Raises:
        AuthenticationError: If the password is wrong.
        ConflictError: If the user already holds the maximum number of live tokens.
    """
    if not verify_password(password, user.hashed_password):
        raise AuthenticationError(DEFAULT_ERROR_WRONG_PASSWORD)

    now = datetime.now(UTC)
    live = await db.scalar(
        select(func.count())
        .select_from(ApiToken)
        .where(ApiToken.user_id == user.id, _live(now))
    )
    if (live or 0) >= DEFAULT_API_TOKEN_MAX_PER_USER:
        raise ConflictError(
            DEFAULT_ERROR_API_TOKEN_LIMIT.format(limit=DEFAULT_API_TOKEN_MAX_PER_USER)
        )

    secret = secrets.token_urlsafe(DEFAULT_API_TOKEN_BYTES)
    plaintext = f"{DEFAULT_API_TOKEN_PREFIX}{secret}"
    scopes = [SCOPE_READ]
    if write:
        scopes.append(SCOPE_WRITE)
    if edit_profile:
        scopes.append(SCOPE_PROFILE)
    token = ApiToken(
        user_id=user.id,
        name=name,
        token_hash=hash_refresh_token(plaintext),
        display_hint=secret[:DEFAULT_API_TOKEN_DISPLAY_CHARS],
        scopes=" ".join(scopes),
        expires_at=now + timedelta(days=expires_in_days),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token, plaintext


async def revoke_token(db: AsyncSession, *, user_id: int, token_id: int) -> None:
    """Revoke one token.

    Args:
        db: Async database session.
        user_id: The owning user.
        token_id: The token to revoke.

    Raises:
        NotFoundError: If the user has no such live token.
    """
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == user_id,
            ApiToken.revoked_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise NotFoundError(DEFAULT_ERROR_API_TOKEN_NOT_FOUND)
    token.revoked_at = datetime.now(UTC)
    await db.commit()


async def revoke_all_tokens(db: AsyncSession, *, user_id: int) -> None:
    """Revoke every token the user holds. The caller commits.

    Args:
        db: Async database session.
        user_id: The owning user.
    """
    await db.execute(
        update(ApiToken)
        .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def resolve(db: AsyncSession, *, plaintext: str) -> ResolvedToken | None:
    """Check a presented token and find its owner.

    Every failure answers the same ``None``: which of unknown, revoked, expired or
    inactive it was is not the caller's business.

    Args:
        db: Async database session.
        plaintext: The token as presented.

    Returns:
        The token's owner and scopes, or None if it cannot be used.
    """
    if not plaintext.startswith(DEFAULT_API_TOKEN_PREFIX):
        return None

    now = datetime.now(UTC)
    result = await db.execute(
        select(ApiToken, User)
        .join(User, User.id == ApiToken.user_id)
        .where(ApiToken.token_hash == hash_refresh_token(plaintext))
    )
    row = result.one_or_none()
    if row is None:
        return None
    token, user = row._tuple()
    expires_at = _aware(token.expires_at)
    if token.revoked_at is not None or expires_at <= now or not user.is_active:
        return None

    last_used = token.last_used_at
    if last_used is None or (now - _aware(last_used)).total_seconds() > (
        DEFAULT_API_TOKEN_TOUCH_SECONDS
    ):
        token.last_used_at = now
        await db.commit()

    return ResolvedToken(
        token_id=token.id,
        user=user,
        scopes=tuple(token.scopes.split()),
        expires_at=expires_at,
    )
