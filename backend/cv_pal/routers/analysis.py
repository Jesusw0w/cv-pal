from fastapi import APIRouter

from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.schemas import (
    CoverageRequest,
    CoverageResponse,
    FindingResponse,
    KeywordResponse,
    ParseabilityResponse,
)
from cv_pal.services import analysis_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/cvs/{cv_id}/ats-check", response_model=ParseabilityResponse)
async def ats_check(
    cv_id: int, current_user: CurrentUser, db: DbSession
) -> ParseabilityResponse:
    """Check whether an applicant tracking system can read a CV.

    Mechanical checks only — no language model is involved, so this works with no
    provider configured, costs nothing, and returns the same result every time.

    Args:
        cv_id: The ID of the CV to check.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The parseability score and findings.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
    """
    report = await analysis_service.ats_check(db, cv_id=cv_id, user_id=current_user.id)
    return ParseabilityResponse(
        score=report.score,
        word_count=report.word_count,
        findings=[FindingResponse.model_validate(f) for f in report.findings],
        blocking=[FindingResponse.model_validate(f) for f in report.blocking],
    )


@router.post("/cvs/{cv_id}/coverage", response_model=CoverageResponse)
async def coverage(
    cv_id: int, payload: CoverageRequest, current_user: CurrentUser, db: DbSession
) -> CoverageResponse:
    """Score a CV against a pasted job description.

    Also deterministic. Missing terms are returned so the caller can show *what* to
    address, not just a number — and required gaps are separated from optional ones.

    Args:
        cv_id: The ID of the CV to score.
        payload: The job description to compare against.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The coverage score with matched and missing terms.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
    """
    report = await analysis_service.keyword_coverage(
        db,
        cv_id=cv_id,
        user_id=current_user.id,
        job_description=payload.job_description,
    )
    return CoverageResponse(
        score=report.score,
        matched=[KeywordResponse.model_validate(k) for k in report.matched],
        missing=[KeywordResponse.model_validate(k) for k in report.missing],
        missing_required=[
            KeywordResponse.model_validate(k) for k in report.missing_required
        ],
    )
