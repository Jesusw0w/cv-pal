"""Job platforms: where the user keeps a profile, and whether it is behind.

Entirely optional. A platform is a name the user chose, a date they state, and a link;
nothing here logs in anywhere or reads a platform's page. "Up to date" means only that
the user updated it on or after the last change to their career profile in CV Pal —
the one thing the app can know.

Ownership is enforced the same way as everywhere else: every query is filtered by
`user_id`.
"""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.constants import (
    DEFAULT_ERROR_PLATFORM_LIMIT,
    DEFAULT_MAX_PLATFORMS,
    PlatformStatus,
)
from cv_pal.exceptions import (
    ConflictError,
    DuplicatePlatformError,
    PlatformNotFoundError,
)
from cv_pal.models import Application, CareerProfile, JobPlatform
from cv_pal.schemas import JobPlatformCreate, JobPlatformUpdate


async def list_platforms(db: AsyncSession, *, user_id: int) -> list[JobPlatform]:
    """Return the user's platforms, by name.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The platforms.
    """
    result = await db.execute(
        select(JobPlatform)
        .where(JobPlatform.user_id == user_id)
        .order_by(JobPlatform.name)
    )
    return list(result.scalars().all())


async def get_owned_platform(
    db: AsyncSession, *, user_id: int, platform_id: int
) -> JobPlatform:
    """Load one of the user's platforms.

    Args:
        db: Async database session.
        user_id: The owning user.
        platform_id: The platform to load.

    Returns:
        The platform.

    Raises:
        PlatformNotFoundError: If it does not exist for this user.
    """
    platform = await db.scalar(
        select(JobPlatform).where(
            JobPlatform.id == platform_id, JobPlatform.user_id == user_id
        )
    )
    if platform is None:
        raise PlatformNotFoundError
    return platform


async def add_platform(
    db: AsyncSession, *, user_id: int, payload: JobPlatformCreate
) -> JobPlatform:
    """Start tracking a platform.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The platform.

    Returns:
        The stored platform.

    Raises:
        ConflictError: If the user already tracks the maximum number.
        DuplicatePlatformError: If a platform by that name is already tracked.
    """
    count = await db.scalar(
        select(func.count())
        .select_from(JobPlatform)
        .where(JobPlatform.user_id == user_id)
    )
    if (count or 0) >= DEFAULT_MAX_PLATFORMS:
        raise ConflictError(
            DEFAULT_ERROR_PLATFORM_LIMIT.format(limit=DEFAULT_MAX_PLATFORMS)
        )

    platform = JobPlatform(user_id=user_id, **payload.model_dump())
    db.add(platform)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicatePlatformError from exc
    await db.refresh(platform)
    return platform


async def update_platform(
    db: AsyncSession, *, user_id: int, platform_id: int, payload: JobPlatformUpdate
) -> JobPlatform:
    """Amend a platform; omitted fields are left alone.

    Args:
        db: Async database session.
        user_id: The owning user.
        platform_id: The platform to amend.
        payload: The fields to change.

    Returns:
        The updated platform.

    Raises:
        PlatformNotFoundError: If it does not exist for this user.
        DuplicatePlatformError: If renamed to a name already tracked.
    """
    platform = await get_owned_platform(db, user_id=user_id, platform_id=platform_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(platform, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicatePlatformError from exc
    await db.refresh(platform)
    return platform


async def delete_platform(db: AsyncSession, *, user_id: int, platform_id: int) -> None:
    """Stop tracking a platform. Applications through it keep, without a platform.

    Args:
        db: Async database session.
        user_id: The owning user.
        platform_id: The platform to delete.

    Raises:
        PlatformNotFoundError: If it does not exist for this user.
    """
    platform = await get_owned_platform(db, user_id=user_id, platform_id=platform_id)
    # `ON DELETE SET NULL` in the schema, done here as well: SQLite enforces no
    # foreign keys, and a dangling id would count those applications under a
    # platform that no longer has a name.
    await db.execute(
        update(Application)
        .where(Application.platform_id == platform_id, Application.user_id == user_id)
        .values(platform_id=None)
    )
    await db.delete(platform)
    await db.commit()


async def profile_changed_at(db: AsyncSession, *, user_id: int) -> datetime | None:
    """When the career profile last changed, roles and skills included.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The time, or None when there is no profile yet.
    """
    changed: datetime | None = await db.scalar(
        select(CareerProfile.updated_at).where(CareerProfile.user_id == user_id)
    )
    return changed


def status_of(platform: JobPlatform, changed_at: datetime | None) -> PlatformStatus:
    """Say whether a platform's copy of the profile is behind.

    Compared by day: a platform updated the same day the profile changed is taken to
    have the change, since the user does both in one sitting.

    Args:
        platform: The platform.
        changed_at: When the career profile last changed.

    Returns:
        The status.
    """
    if platform.profile_updated_on is None:
        return PlatformStatus.UNKNOWN
    if changed_at is None or platform.profile_updated_on >= changed_at.date():
        return PlatformStatus.UP_TO_DATE
    return PlatformStatus.OUTDATED
