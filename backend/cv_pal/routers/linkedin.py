from typing import Annotated

from fastapi import APIRouter, Form, UploadFile, status

from cv_pal.constants import (
    DEFAULT_ERROR_LINKEDIN_AMBIGUOUS_INPUT,
    DEFAULT_ERROR_LINKEDIN_NEEDS_INPUT,
    DEFAULT_MAX_LINKEDIN_PASTE_LENGTH,
    DEFAULT_MIN_LINKEDIN_PASTE_LENGTH,
)
from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.exceptions import ValidationError
from cv_pal.schemas import (
    CoverageResponse,
    KeywordResponse,
    LinkedInIssueResponse,
    LinkedInProfileResponse,
    LinkedInReviewResponse,
    LinkedInSectionResponse,
)
from cv_pal.services import linkedin_service

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

PastedProfile = Annotated[
    str | None,
    Form(
        min_length=DEFAULT_MIN_LINKEDIN_PASTE_LENGTH,
        max_length=DEFAULT_MAX_LINKEDIN_PASTE_LENGTH,
        description="Profile text, for the copy-and-paste route.",
    ),
]


@router.post(
    "/import",
    response_model=LinkedInProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_profile(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile | None = None,
    text: PastedProfile = None,
) -> LinkedInProfileResponse:
    """Import a LinkedIn profile the user exported themselves.

    Accepts a print-to-PDF or "Save to PDF" of the profile page, the official data
    export archive, or pasted text — the routes documented in
    `docs/linkedin-import.md`. **There is no URL route**: fetching a profile is
    automated access under LinkedIn's terms and the account at risk is the user's own.

    Any previous snapshot is replaced.

    Args:
        current_user: The authenticated user.
        db: Async database session.
        file: A profile PDF or data-export ZIP.
        text: Profile text, when pasting instead.

    Returns:
        The stored snapshot.

    Raises:
        ValidationError: If neither or both of file and text were sent.
        LinkedInUnreadableError: If the document does not read as a LinkedIn profile.
        LinkedInExportEmptyError: If an archive carried no profile files.
    """
    # A multipart form makes "both" expressible, so it is rejected rather than silently
    # resolved — the user would not be able to tell which one was used.
    if file is not None and text is not None:
        raise ValidationError(DEFAULT_ERROR_LINKEDIN_AMBIGUOUS_INPUT)
    if file is None and text is None:
        raise ValidationError(DEFAULT_ERROR_LINKEDIN_NEEDS_INPUT)

    stored = await linkedin_service.import_profile(
        db, user_id=current_user.id, file=file, text=text
    )
    return LinkedInProfileResponse.model_validate(stored)


@router.get("", response_model=LinkedInProfileResponse)
async def get_profile(
    current_user: CurrentUser, db: DbSession
) -> LinkedInProfileResponse:
    """Return the imported LinkedIn snapshot.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored snapshot.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    stored = await linkedin_service.get_profile(db, user_id=current_user.id)
    return LinkedInProfileResponse.model_validate(stored)


@router.get("/review", response_model=LinkedInReviewResponse)
async def review_profile(
    current_user: CurrentUser, db: DbSession
) -> LinkedInReviewResponse:
    """Review the imported profile section by section.

    Deterministic throughout — no language model is involved, so this works on a fresh
    install with nothing configured. The review compares the profile against itself
    (per-section completeness), against the user's target roles (recruiter-search
    keyword coverage), and against the career profile (dates, titles and employers that
    disagree between the two).

    Recomputed on each request, because the goals and career profile it is measured
    against change more often than the snapshot does.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The review.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    result = await linkedin_service.review_profile(db, user_id=current_user.id)

    coverage = (
        CoverageResponse(
            score=result.coverage.score,
            matched=[
                KeywordResponse.model_validate(k) for k in result.coverage.matched
            ],
            missing=[
                KeywordResponse.model_validate(k) for k in result.coverage.missing
            ],
            missing_required=[
                KeywordResponse.model_validate(k)
                for k in result.coverage.missing_required
            ],
        )
        if result.coverage is not None
        else None
    )

    return LinkedInReviewResponse(
        score=result.score,
        source=result.source,
        note=result.note,
        sections=[
            LinkedInSectionResponse.model_validate(section)
            for section in result.sections
        ],
        consistency=[
            LinkedInIssueResponse.model_validate(issue) for issue in result.consistency
        ],
        coverage=coverage,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(current_user: CurrentUser, db: DbSession) -> None:
    """Delete the imported LinkedIn snapshot.

    A profile export is a sensitive document, so removing it is a first-class action
    rather than something only account deletion can do.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    await linkedin_service.delete_profile(db, user_id=current_user.id)
