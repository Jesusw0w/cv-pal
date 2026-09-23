"""Job platforms the user keeps a profile on, and whether each is behind."""

from datetime import datetime

from fastapi import APIRouter, status

from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.models import JobPlatform
from cv_pal.schemas import JobPlatformCreate, JobPlatformResponse, JobPlatformUpdate
from cv_pal.services import platform_service

router = APIRouter(prefix="/platforms", tags=["platforms"])


def _response(
    platform: JobPlatform, changed_at: datetime | None
) -> JobPlatformResponse:
    """Shape a platform for the API, with its status against the profile.

    Args:
        platform: The platform.
        changed_at: When the career profile last changed.

    Returns:
        The response model.
    """
    return JobPlatformResponse(
        id=platform.id,
        name=platform.name,
        profile_url=platform.profile_url,
        profile_updated_on=platform.profile_updated_on,
        notes=platform.notes,
        status=platform_service.status_of(platform, changed_at),
    )


@router.get("", response_model=list[JobPlatformResponse])
async def list_platforms(
    current_user: CurrentUser, db: DbSession
) -> list[JobPlatformResponse]:
    """List the user's platforms, by name.

    Returns:
        The platforms, each saying whether its copy of the profile is behind.
    """
    platforms = await platform_service.list_platforms(db, user_id=current_user.id)
    changed_at = await platform_service.profile_changed_at(db, user_id=current_user.id)
    return [_response(platform, changed_at) for platform in platforms]


@router.post(
    "", response_model=JobPlatformResponse, status_code=status.HTTP_201_CREATED
)
async def add_platform(
    payload: JobPlatformCreate, current_user: CurrentUser, db: DbSession
) -> JobPlatformResponse:
    """Start tracking a platform.

    Args:
        payload: The platform.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored platform.
    """
    platform = await platform_service.add_platform(
        db, user_id=current_user.id, payload=payload
    )
    changed_at = await platform_service.profile_changed_at(db, user_id=current_user.id)
    return _response(platform, changed_at)


@router.patch("/{platform_id}", response_model=JobPlatformResponse)
async def update_platform(
    platform_id: int,
    payload: JobPlatformUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> JobPlatformResponse:
    """Amend a platform — most often, to record that it was just brought up to date.

    Args:
        platform_id: The platform to amend.
        payload: The fields to change; omitted fields are left alone.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated platform.
    """
    platform = await platform_service.update_platform(
        db, user_id=current_user.id, platform_id=platform_id, payload=payload
    )
    changed_at = await platform_service.profile_changed_at(db, user_id=current_user.id)
    return _response(platform, changed_at)


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform(
    platform_id: int, current_user: CurrentUser, db: DbSession
) -> None:
    """Stop tracking a platform. Applications sent through it are kept.

    Args:
        platform_id: The platform to delete.
        current_user: The authenticated user.
        db: Async database session.
    """
    await platform_service.delete_platform(
        db, user_id=current_user.id, platform_id=platform_id
    )
