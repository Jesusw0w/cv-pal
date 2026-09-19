"""Applications: what was sent, what came back, and how the search is actually going.

The last step of the journey. Everything before it — the profile, the tailoring, the
match scores — is preparation, and until this existed the product could not see whether
any of it worked. That is not only a missing screen: reply rate per CV version is the
one measurement that tells a user which of their documents is doing its job, and it
cannot be computed from postings and CVs alone.

Ownership is enforced the same way as everywhere else: every query is filtered by
`user_id`, and no endpoint accepts an application id without it.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cv_pal.constants import (
    CLOSED_APPLICATION_STATUSES,
    DEFAULT_APPLICATION_STALE_DAYS,
    REPLIED_APPLICATION_STATUSES,
    ApplicationStatus,
)
from cv_pal.exceptions import ApplicationNotFoundError, DuplicateApplicationError
from cv_pal.models import Application, JobPosting
from cv_pal.schemas import ApplicationCreate, ApplicationUpdate
from cv_pal.services.cv_service import get_owned_cv
from cv_pal.services.job_service import get_posting


def days_since(applied_at: date) -> int:
    """Days between an application going out and today.

    Args:
        applied_at: When it was sent.

    Returns:
        The interval in days, never negative — the schema refuses a future date.
    """
    return (date.today() - applied_at).days


def needs_chasing(application: Application) -> bool:
    """Report whether an application has gone quiet for long enough to chase.

    Only ones still open: a rejection is an answer, and nagging the user to follow up on
    a role they did not get is the fastest way to make them ignore the whole feature.

    Args:
        application: The application to judge.

    Returns:
        True when it is still open and older than the stale threshold.
    """
    if application.status in CLOSED_APPLICATION_STATUSES:
        return False
    if application.status in REPLIED_APPLICATION_STATUSES:
        # Already talking. The clock that matters now runs from the last movement.
        return (
            days_since(application.status_changed_at) > DEFAULT_APPLICATION_STALE_DAYS
        )
    return days_since(application.applied_at) > DEFAULT_APPLICATION_STALE_DAYS


async def list_applications(db: AsyncSession, *, user_id: int) -> list[Application]:
    """Return the user's applications, most recently sent first.

    Returns:
        The applications, each with its posting loaded.
    """
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .options(selectinload(Application.posting))
        .order_by(Application.applied_at.desc(), Application.id.desc())
    )
    return list(result.scalars().all())


async def _owned_application(
    db: AsyncSession, *, user_id: int, application_id: int
) -> Application:
    """Fetch an application belonging to this user.

    Args:
        db: Async database session.
        user_id: The owning user.
        application_id: The application to fetch.

    Returns:
        The application, with its posting loaded.

    Raises:
        ApplicationNotFoundError: If it does not exist for this user.
    """
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id, Application.user_id == user_id)
        .options(selectinload(Application.posting))
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ApplicationNotFoundError
    return application


async def record_application(
    db: AsyncSession, *, user_id: int, payload: ApplicationCreate
) -> Application:
    """Record that an application went out.

    Both references are resolved through the services that own them, so a posting or a
    CV belonging to somebody else is a 404 rather than a foreign key that happens to
    resolve.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The posting applied for, and what was sent.

    Returns:
        The created application, with its posting loaded.

    Raises:
        PostingNotFoundError: If the posting is not this user's.
        CVNotFoundError: If the CV is not this user's.
        DuplicateApplicationError: If this posting was already applied for.
    """
    await get_posting(db, user_id=user_id, posting_id=payload.job_posting_id)
    if payload.cv_id is not None:
        await get_owned_cv(db, cv_id=payload.cv_id, user_id=user_id)

    applied_at = payload.applied_at or date.today()
    application = Application(
        user_id=user_id,
        job_posting_id=payload.job_posting_id,
        cv_id=payload.cv_id,
        status=ApplicationStatus.APPLIED,
        applied_at=applied_at,
        # Nothing has moved yet, so the status is as old as the application.
        status_changed_at=applied_at,
        notes=payload.notes,
    )
    db.add(application)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateApplicationError from exc

    return await _owned_application(db, user_id=user_id, application_id=application.id)


async def update_application(
    db: AsyncSession, *, user_id: int, application_id: int, payload: ApplicationUpdate
) -> Application:
    """Move an application along, or amend what was recorded.

    `status_changed_at` moves only when the status actually changes, so correcting a
    typo in the notes does not reset the clock that decides what needs chasing.

    Args:
        db: Async database session.
        user_id: The owning user.
        application_id: The application to amend.
        payload: The fields to change; omitted fields are left alone.

    Returns:
        The updated application.

    Raises:
        ApplicationNotFoundError: If it does not exist for this user.
        CVNotFoundError: If a newly cited CV is not this user's.
    """
    application = await _owned_application(
        db, user_id=user_id, application_id=application_id
    )
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("cv_id") is not None:
        await get_owned_cv(db, cv_id=changes["cv_id"], user_id=user_id)

    status = changes.get("status")
    if status is not None and status != application.status:
        application.status_changed_at = date.today()

    for field, value in changes.items():
        setattr(application, field, value)
    await db.commit()
    return await _owned_application(db, user_id=user_id, application_id=application_id)


async def delete_application(
    db: AsyncSession, *, user_id: int, application_id: int
) -> None:
    """Remove an application record.

    Args:
        db: Async database session.
        user_id: The owning user.
        application_id: The application to remove.

    Raises:
        ApplicationNotFoundError: If it does not exist for this user.
    """
    application = await _owned_application(
        db, user_id=user_id, application_id=application_id
    )
    await db.delete(application)
    await db.commit()


async def applied_posting_ids(db: AsyncSession, *, user_id: int) -> set[int]:
    """Return the postings this user has already applied for.

    Lets the job list mark them without a query per posting.

    Returns:
        The posting ids.
    """
    result = await db.execute(
        select(Application.job_posting_id).where(Application.user_id == user_id)
    )
    return set(result.scalars().all())


def summarise(applications: list[Application]) -> dict[str, object]:
    """Reduce a list of applications to the figures worth showing.

    Reply rate is computed over applications old enough to have been answered. Counting
    the ones sent this week as unanswered would make every active search look like a
    failing one, which is both wrong and the sort of number that makes people stop
    looking at a dashboard.

    Args:
        applications: The user's applications.

    Returns:
        The fields of `ApplicationStatsResponse`.
    """
    by_status = dict.fromkeys(ApplicationStatus, 0)
    for application in applications:
        by_status[application.status] += 1

    replied = sum(1 for a in applications if a.status in REPLIED_APPLICATION_STATUSES)
    cutoff = date.today() - timedelta(days=DEFAULT_APPLICATION_STALE_DAYS)
    answerable = sum(
        1
        for a in applications
        if a.applied_at <= cutoff or a.status in REPLIED_APPLICATION_STATUSES
    )

    return {
        "total": len(applications),
        "by_status": by_status,
        "replied": replied,
        "answerable": answerable,
        # None, not zero: "no reply rate yet" and "nobody has replied" are different
        # facts, and showing 0% to someone who applied yesterday is just untrue.
        "reply_rate": round(replied / answerable * 100) if answerable else None,
        "needs_chasing": sum(1 for a in applications if needs_chasing(a)),
    }


async def postings_without_applications(
    db: AsyncSession, *, user_id: int
) -> list[JobPosting]:
    """Saved postings the user has not recorded an application for.

    Returns:
        The postings, newest first.
    """
    applied = await applied_posting_ids(db, user_id=user_id)
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.user_id == user_id)
        .order_by(JobPosting.created_at.desc())
    )
    return [posting for posting in result.scalars().all() if posting.id not in applied]
