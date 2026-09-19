from typing import Annotated

from fastapi import APIRouter, Query, UploadFile, status

from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.schemas import CVResponse
from cv_pal.services import cv_service

router = APIRouter(prefix="/cvs", tags=["cvs"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/", response_model=CVResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile, current_user: CurrentUser, db: DbSession
) -> CVResponse:
    """Upload a new CV document.

    Args:
        file: The CV file to upload (PDF or DOCX).
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The created CV metadata.

    Raises:
        ValidationError: If the file type, content or size is invalid.
    """
    cv = await cv_service.create_cv(db, user_id=current_user.id, file=file)
    return CVResponse.model_validate(cv)


@router.get("/", response_model=list[CVResponse])
async def list_cvs(
    current_user: CurrentUser,
    db: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[CVResponse]:
    """List the current user's CVs, newest first.

    Args:
        current_user: The authenticated user.
        db: Async database session.
        limit: Maximum number of CVs to return.
        offset: Number of CVs to skip.

    Returns:
        The user's CV metadata.
    """
    cvs = await cv_service.list_cvs(
        db, user_id=current_user.id, limit=limit, offset=offset
    )
    return [CVResponse.model_validate(cv) for cv in cvs]


@router.get("/{cv_id}", response_model=CVResponse)
async def get_cv(cv_id: int, current_user: CurrentUser, db: DbSession) -> CVResponse:
    """Get a specific CV by ID.

    Args:
        cv_id: The ID of the CV to retrieve.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The CV metadata.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
    """
    cv = await cv_service.get_owned_cv(db, cv_id=cv_id, user_id=current_user.id)
    return CVResponse.model_validate(cv)


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(cv_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Delete a CV and its stored file.

    Args:
        cv_id: The ID of the CV to delete.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
    """
    await cv_service.delete_cv(db, cv_id=cv_id, user_id=current_user.id)
