from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.analysis import (
    CoverageReport,
    ParseabilityReport,
    analyse,
    check_parseability,
)
from cv_pal.parsing import extract_cv_text
from cv_pal.services.cv_service import get_owned_cv


async def _cv_text(db: AsyncSession, *, cv_id: int, user_id: int) -> str:
    """Load a user's CV and extract its text.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV.
        user_id: Identifier of the owning user.

    Returns:
        The extracted text.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
        UnsupportedFileTypeError: If the stored file cannot be parsed.
    """
    cv = await get_owned_cv(db, cv_id=cv_id, user_id=user_id)
    return await extract_cv_text(Path(cv.file_path))


async def ats_check(
    db: AsyncSession, *, cv_id: int, user_id: int
) -> ParseabilityReport:
    """Check whether an applicant tracking system can read a CV.

    Runs no model: the checks are mechanical, so this works with no LLM configured and
    costs nothing.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV.
        user_id: Identifier of the owning user.

    Returns:
        The parseability report.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
    """
    return check_parseability(await _cv_text(db, cv_id=cv_id, user_id=user_id))


async def keyword_coverage(
    db: AsyncSession, *, cv_id: int, user_id: int, job_description: str
) -> CoverageReport:
    """Score a CV against a job description's keywords.

    Also deterministic — the same CV and posting always give the same score, which is
    what makes the number worth showing a user.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV.
        user_id: Identifier of the owning user.
        job_description: The posting text to compare against.

    Returns:
        The coverage report.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
    """
    text = await _cv_text(db, cv_id=cv_id, user_id=user_id)
    return analyse(text, job_description)
