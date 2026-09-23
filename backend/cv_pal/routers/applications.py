from fastapi import APIRouter, status

from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.models import Application
from cv_pal.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatsResponse,
    ApplicationUpdate,
    JobPostingResponse,
)
from cv_pal.services import application_service, platform_service

router = APIRouter(prefix="/applications", tags=["applications"])


def _response(application: Application) -> ApplicationResponse:
    """Shape an application for the API.

    The two derived fields are computed here rather than stored: both change with the
    passing of a day, and a copy written into the row would be wrong by morning.

    Args:
        application: The application, with its posting loaded.

    Returns:
        The response model.
    """
    return ApplicationResponse(
        id=application.id,
        status=application.status,
        applied_at=application.applied_at,
        status_changed_at=application.status_changed_at,
        cv_id=application.cv_id,
        platform_id=application.platform_id,
        salary=application.salary,
        next_step=application.next_step,
        notes=application.notes,
        posting=JobPostingResponse.model_validate(application.posting),
        days_since_applied=application_service.days_since(application.applied_at),
        needs_chasing=application_service.needs_chasing(application),
    )


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    current_user: CurrentUser, db: DbSession
) -> list[ApplicationResponse]:
    """List the user's applications, most recently sent first.

    Returns:
        The applications.
    """
    applications = await application_service.list_applications(
        db, user_id=current_user.id
    )
    return [_response(application) for application in applications]


@router.get("/stats", response_model=ApplicationStatsResponse)
async def application_stats(
    current_user: CurrentUser, db: DbSession
) -> ApplicationStatsResponse:
    """Report how the search is going.

    Declared before `/{application_id}` or the path is read as an id.

    Returns:
        Counts per status, reply rate, and how many applications have gone quiet.
    """
    applications = await application_service.list_applications(
        db, user_id=current_user.id
    )
    platforms = await platform_service.list_platforms(db, user_id=current_user.id)
    return ApplicationStatsResponse.model_validate(
        application_service.summarise(applications, platforms)
    )


@router.get("/unapplied", response_model=list[JobPostingResponse])
async def postings_without_applications(
    current_user: CurrentUser, db: DbSession
) -> list[JobPostingResponse]:
    """List saved postings with no application recorded against them.

    What the user can act on next, and the only list that shrinks as a search
    progresses.

    Returns:
        The postings, newest first.
    """
    postings = await application_service.postings_without_applications(
        db, user_id=current_user.id
    )
    return [JobPostingResponse.model_validate(posting) for posting in postings]


@router.post(
    "", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def record_application(
    payload: ApplicationCreate, current_user: CurrentUser, db: DbSession
) -> ApplicationResponse:
    """Record that an application went out.

    Args:
        payload: The posting applied for, and what was sent with it.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The created application.

    Raises:
        PostingNotFoundError: If the posting is not this user's.
        CVNotFoundError: If the CV is not this user's.
        DuplicateApplicationError: If this posting was already applied for.
    """
    application = await application_service.record_application(
        db, user_id=current_user.id, payload=payload
    )
    return _response(application)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ApplicationResponse:
    """Move an application along, or amend what was recorded.

    Args:
        application_id: The application to amend.
        payload: The fields to change; omitted fields are left alone.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated application.

    Raises:
        ApplicationNotFoundError: If it does not exist for this user.
    """
    application = await application_service.update_application(
        db, user_id=current_user.id, application_id=application_id, payload=payload
    )
    return _response(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int, current_user: CurrentUser, db: DbSession
) -> None:
    """Remove an application record.

    The posting itself stays saved: forgetting that you applied is not the same as no
    longer being interested.

    Args:
        application_id: The application to remove.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        ApplicationNotFoundError: If it does not exist for this user.
    """
    await application_service.delete_application(
        db, user_id=current_user.id, application_id=application_id
    )
