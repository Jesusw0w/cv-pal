from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal import storage
from cv_pal.exceptions import CVNotFoundError
from cv_pal.models import CV


async def get_owned_cv(db: AsyncSession, *, cv_id: int, user_id: int) -> CV:
    """Fetch a CV belonging to a specific user.

    Ownership is part of the lookup rather than a separate check, so a CV belonging to
    another user is indistinguishable from one that does not exist.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV.
        user_id: Identifier of the owning user.

    Returns:
        The matching CV.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
    """
    result = await db.execute(select(CV).where(CV.id == cv_id, CV.user_id == user_id))
    cv = result.scalar_one_or_none()
    if cv is None:
        raise CVNotFoundError
    return cv


async def list_cvs(
    db: AsyncSession, *, user_id: int, limit: int, offset: int
) -> list[CV]:
    """List a user's CVs, newest first.

    Args:
        db: Async database session.
        user_id: Identifier of the owning user.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip.

    Returns:
        The user's CVs.
    """
    result = await db.execute(
        select(CV)
        .where(CV.user_id == user_id)
        .order_by(CV.created_at.desc(), CV.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create_cv(db: AsyncSession, *, user_id: int, file: UploadFile) -> CV:
    """Store an uploaded CV and record it against the user.

    Args:
        db: Async database session.
        user_id: Identifier of the owning user.
        file: The uploaded CV file.

    Returns:
        The newly created CV record.

    Raises:
        ValidationError: If the upload fails validation.
    """
    stored_path = await storage.save_upload(file)

    # max, not count: after a delete, count + 1 would reuse a live version number.
    version_result = await db.execute(
        select(func.max(CV.version)).where(CV.user_id == user_id)
    )
    next_version = (version_result.scalar_one() or 0) + 1

    cv = CV(
        user_id=user_id,
        filename=file.filename or stored_path.name,
        file_path=str(stored_path),
        version=next_version,
    )
    db.add(cv)
    try:
        await db.commit()
    except Exception:
        # Never leave an orphaned file behind if the row could not be written.
        await storage.delete_file(stored_path)
        await db.rollback()
        raise
    await db.refresh(cv)
    return cv


async def delete_cv(db: AsyncSession, *, cv_id: int, user_id: int) -> None:
    """Delete a CV and its stored file.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV to delete.
        user_id: Identifier of the owning user.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
    """
    cv = await get_owned_cv(db, cv_id=cv_id, user_id=user_id)
    stored_path = Path(cv.file_path)

    await db.delete(cv)
    await db.commit()
    # The row is the source of truth; remove the file only once it is gone.
    await storage.delete_file(stored_path)
