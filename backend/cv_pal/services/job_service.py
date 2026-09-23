"""Job postings: saving them, and scoring them against the user's own goals.

Ownership is enforced by resolving every posting from the user, so a request can only
ever reach rows belonging to that account.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.analysis.matching import MatchScore, score_posting, title_match
from cv_pal.constants import EmploymentType, JobSource, WorkRegime
from cv_pal.exceptions import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    DuplicatePostingError,
    JobBoardError,
    PostingNotFoundError,
    UnlistableSourceError,
    UnsupportedJobUrlError,
)
from cv_pal.integrations.job_boards import board_by_source, board_for
from cv_pal.models import CareerProfile, JobBoardConnection, JobPosting
from cv_pal.schemas import AppliedRole, JobBoardConnectionCreate, JobPostingCreate
from cv_pal.services.profile_service import get_or_create_goals, get_or_create_profile

# How much of a target role's wording a posting's title has to carry before a filtered
# sync will save it. Half, so "Backend Engineer" catches "Senior Backend Engineer" and
# "Backend Engineer II" without also catching every role that happens to say "Engineer"
# — and the count of what it turned away is reported, so a threshold that is wrong for
# one search is visible rather than silent.
MIN_TITLE_MATCH = 0.5


@dataclass(frozen=True, slots=True)
class SyncResult:
    """What one board sync did."""

    connection_id: int
    found: int
    added: int
    # Postings the board offered that the goal filter turned away. Reported rather than
    # dropped quietly: a filter the user cannot see is one they cannot correct.
    skipped: int
    error: str | None


def content_hash(title: str, company: str | None, description: str) -> str:
    """Fingerprint a posting so the same role saved twice collapses to one.

    Hashes the normalised title, company and description rather than the URL, because
    the identical role is routinely posted to several boards under different links —
    which is exactly the duplicate worth collapsing.

    Args:
        title: The posting's title.
        company: The hiring company, when known.
        description: The posting text.

    Returns:
        A hex SHA-256 digest.
    """
    normalised = "\n".join(
        " ".join(part.casefold().split())
        for part in (title, company or "", description)
    )
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


async def list_postings(db: AsyncSession, *, user_id: int) -> list[JobPosting]:
    """Return the user's saved postings, newest first.

    Returns:
        The postings.
    """
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.user_id == user_id)
        .order_by(JobPosting.created_at.desc())
    )
    return list(result.scalars().all())


async def get_posting(db: AsyncSession, *, user_id: int, posting_id: int) -> JobPosting:
    """Return one of the user's postings.

    Args:
        db: Async database session.
        user_id: The owning user.
        posting_id: The posting to return.

    Returns:
        The posting.

    Raises:
        PostingNotFoundError: If it does not exist for this user.
    """
    result = await db.execute(
        select(JobPosting).where(
            JobPosting.id == posting_id, JobPosting.user_id == user_id
        )
    )
    posting = result.scalar_one_or_none()
    if posting is None:
        raise PostingNotFoundError
    return posting


async def save_pasted(
    db: AsyncSession, *, user_id: int, payload: JobPostingCreate
) -> JobPosting:
    """Save a posting the user pasted.

    The path that always works: no board to be unavailable, no layout to change, no
    terms to breach. Every other route falls back to it.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The posting.

    Returns:
        The stored posting.

    Raises:
        DuplicatePostingError: If this user already saved the same posting.
    """
    return await _store(
        db,
        user_id=user_id,
        source=JobSource.MANUAL,
        external_id=None,
        source_url=payload.source_url,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        description=payload.description,
    )


async def save_role(db: AsyncSession, *, user_id: int, role: AppliedRole) -> JobPosting:
    """Save the role behind an application that has no posting text.

    Stored as a manual posting with an empty description, so it is scored on its title
    alone — and the score's reasons say the skills could not be judged.

    Args:
        db: Async database session.
        user_id: The owning user.
        role: The title, company and link that are known.

    Returns:
        The stored posting.

    Raises:
        DuplicatePostingError: If the same role is already saved.
    """
    return await _store(
        db,
        user_id=user_id,
        source=JobSource.MANUAL,
        external_id=None,
        source_url=role.source_url,
        title=role.title,
        company=role.company,
        location=role.location,
        description="",
    )


async def save_from_url(
    db: AsyncSession, *, user_id: int, url: str, client: httpx.AsyncClient
) -> JobPosting:
    """Save a posting from a link to a job board CV Pal can read.

    Only sanctioned ATS boards are resolved, and always through their own API rather
    than by fetching the page — see `integrations/job_boards.py` for why there is no
    general fetcher.

    Args:
        db: Async database session.
        user_id: The owning user.
        url: The posting URL.
        client: The HTTP client to read the board with.

    Returns:
        The stored posting.

    Raises:
        UnsupportedJobUrlError: If no sanctioned board recognises the URL.
        JobBoardError: If the board could not be read.
        DuplicatePostingError: If this user already saved the same posting.
    """
    board = board_for(url)
    if board is None:
        raise UnsupportedJobUrlError

    found = await board.fetch(client, url)
    return await _store(
        db,
        user_id=user_id,
        source=found.source,
        external_id=found.external_id,
        source_url=found.url,
        title=found.title,
        company=found.company,
        location=found.location,
        description=found.description,
        employment_type=found.employment_type,
    )


async def delete_posting(db: AsyncSession, *, user_id: int, posting_id: int) -> None:
    """Remove a posting.

    Args:
        db: Async database session.
        user_id: The owning user.
        posting_id: The posting to remove.

    Raises:
        PostingNotFoundError: If it does not exist for this user.
    """
    posting = await get_posting(db, user_id=user_id, posting_id=posting_id)
    await db.delete(posting)
    await db.commit()


async def score(db: AsyncSession, *, user_id: int, posting: JobPosting) -> MatchScore:
    """Score a posting against this user's profile and goals.

    Args:
        db: Async database session.
        user_id: The owning user.
        posting: The posting to score.

    Returns:
        The score with its reasons.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    goals = await get_or_create_goals(db, user_id=user_id)

    return score_posting(
        title=posting.title,
        description=posting.description,
        location=posting.location,
        company=posting.company,
        profile_text=profile_as_text(profile),
        target_roles=list(goals.target_roles),
        work_regimes=[WorkRegime(value) for value in goals.work_regimes],
        regime_non_negotiable=goals.regime_non_negotiable,
        work_locations=list(goals.work_locations),
        location_non_negotiable=goals.location_non_negotiable,
    )


def profile_as_text(profile: CareerProfile) -> str:
    """Flatten a profile into the text the keyword analysis reads.

    **Only evidenced skills are included.** An unevidenced skill is a claim the user has
    not backed with a dated role, and letting it raise a match score would rank a job by
    experience the user cannot demonstrate — the same rule that stops a generated CV
    claiming it.

    Args:
        profile: The user's career profile.

    Returns:
        The profile as plain text.
    """
    parts = [profile.headline or "", profile.summary or ""]
    parts += [skill.name for skill in profile.skills if skill.is_evidenced]
    parts += [
        f"{experience.title} {experience.organisation} {experience.description or ''}"
        for experience in profile.experiences
    ]
    return "\n".join(part for part in parts if part.strip())


async def _store(
    db: AsyncSession,
    *,
    user_id: int,
    source: JobSource,
    external_id: str | None,
    source_url: str | None,
    title: str,
    company: str | None,
    location: str | None,
    description: str,
    employment_type: EmploymentType | None = None,
) -> JobPosting:
    """Persist a posting, refusing one this user already has.

    Args:
        db: Async database session.
        user_id: The owning user.
        source: Where it came from.
        external_id: The board's own identifier, when there is one.
        source_url: A link back to the posting.
        title: The posting's title.
        company: The hiring company.
        location: The posting's location.
        description: The posting text.
        employment_type: The contract offered, when the source states one.

    Returns:
        The stored posting.

    Raises:
        DuplicatePostingError: If the same posting is already saved.
    """
    digest = content_hash(title, company, description)

    existing = await db.execute(
        select(JobPosting).where(
            JobPosting.user_id == user_id, JobPosting.content_hash == digest
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicatePostingError

    posting = JobPosting(
        user_id=user_id,
        source=source,
        external_id=external_id,
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        description=description,
        employment_type=employment_type,
        content_hash=digest,
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


__all__ = [
    "content_hash",
    "delete_posting",
    "get_posting",
    "list_postings",
    "profile_as_text",
    "save_from_url",
    "save_pasted",
    "score",
]


async def list_connections(
    db: AsyncSession, *, user_id: int
) -> list[JobBoardConnection]:
    """Return the boards this user is watching.

    Returns:
        The connections, oldest first.
    """
    result = await db.execute(
        select(JobBoardConnection)
        .where(JobBoardConnection.user_id == user_id)
        .order_by(JobBoardConnection.created_at)
    )
    return list(result.scalars().all())


async def add_connection(
    db: AsyncSession, *, user_id: int, payload: JobBoardConnectionCreate
) -> JobBoardConnection:
    """Watch a company's board.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The board to watch.

    Returns:
        The stored connection.

    Raises:
        UnlistableSourceError: If the source has no board behind it.
        DuplicateConnectionError: If the user already watches that board.
    """
    if board_by_source(payload.source) is None:
        raise UnlistableSourceError

    existing = await db.execute(
        select(JobBoardConnection).where(
            JobBoardConnection.user_id == user_id,
            JobBoardConnection.source == payload.source,
            JobBoardConnection.identifier == payload.identifier,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateConnectionError

    connection = JobBoardConnection(
        user_id=user_id,
        source=payload.source,
        identifier=payload.identifier,
        label=payload.label or payload.identifier.replace("-", " ").title(),
        filter_by_goals=payload.filter_by_goals,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


async def delete_connection(
    db: AsyncSession, *, user_id: int, connection_id: int
) -> None:
    """Stop watching a board. Postings already saved from it are kept.

    Args:
        db: Async database session.
        user_id: The owning user.
        connection_id: The connection to remove.

    Raises:
        ConnectionNotFoundError: If it does not exist for this user.
    """
    connection = await _get_connection(db, user_id=user_id, connection_id=connection_id)
    await db.delete(connection)
    await db.commit()


async def sync_connection(
    db: AsyncSession,
    *,
    user_id: int,
    connection_id: int,
    client: httpx.AsyncClient,
) -> SyncResult:
    """Fetch a board and save everything on it that is not already saved.

    Idempotent by content hash, so running it on a schedule re-saves nothing: a board
    that has not changed produces zero additions. That is what makes it safe to call on
    a timer without any de-duplication logic in the caller.

    A board failure is recorded on the connection rather than raised, so one unreachable
    company does not fail a sweep across all of them.

    Args:
        db: Async database session.
        user_id: The owning user.
        connection_id: The connection to sync.
        client: The HTTP client to read the board with.

    Returns:
        What the sync did.

    Raises:
        ConnectionNotFoundError: If the connection does not exist for this user.
    """
    connection = await _get_connection(db, user_id=user_id, connection_id=connection_id)
    board = board_by_source(connection.source)
    if board is None:  # pragma: no cover - guarded when the connection is created
        raise UnlistableSourceError

    try:
        found = await board.list_board(client, connection.identifier)
    except JobBoardError as exc:
        connection.last_error = str(exc)
        connection.last_synced_at = datetime.now(UTC)
        await db.commit()
        return SyncResult(
            connection_id=connection.id, found=0, added=0, skipped=0, error=str(exc)
        )

    # Only when the user asked for it, and only when there is something to match
    # against: an empty goal list would otherwise reject the entire board.
    wanted: list[str] = []
    if connection.filter_by_goals:
        goals = await get_or_create_goals(db, user_id=user_id)
        wanted = list(goals.target_roles)

    added = 0
    skipped = 0
    for posting in found:
        if wanted and title_match(posting.title, wanted) < MIN_TITLE_MATCH:
            skipped += 1
            continue
        try:
            await _store(
                db,
                user_id=user_id,
                source=posting.source,
                external_id=posting.external_id,
                source_url=posting.url or None,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                description=posting.description,
                employment_type=posting.employment_type,
            )
            added += 1
        except DuplicatePostingError:
            # Already saved. The expected outcome on every sync after the first.
            continue

    connection.last_error = None
    connection.last_synced_at = datetime.now(UTC)
    await db.commit()
    return SyncResult(
        connection_id=connection.id,
        found=len(found),
        added=added,
        skipped=skipped,
        error=None,
    )


async def sync_all_connections(
    db: AsyncSession, *, user_id: int, client: httpx.AsyncClient
) -> list[SyncResult]:
    """Sync every source this user watches, in one call.

    **This is what makes the documented cron story true.** Per-connection sync needs
    the caller to know the ids, so a nightly entry meant one command per source and a
    rewrite every time the user watched another. One endpoint means one line in crontab
    that keeps working as the watch list changes.

    Sequential rather than concurrent on purpose: the sources are third-party APIs
    whose terms ask for modest request rates — Remotive's asks for a handful of calls a
    day — and a self-hosted user syncing a few boards gains nothing from parallelism
    that would be worth looking like a burst to someone else's server.

    Args:
        db: Async database session.
        user_id: The owning user.
        client: The HTTP client to read the boards with.

    Returns:
        One result per watched source, in the order they were added. A source that
        could not be read contributes a result carrying its error rather than aborting
        the sweep — the same rule as a single sync, applied across all of them.
    """
    connections = await list_connections(db, user_id=user_id)
    return [
        await sync_connection(
            db, user_id=user_id, connection_id=connection.id, client=client
        )
        for connection in connections
    ]


async def _get_connection(
    db: AsyncSession, *, user_id: int, connection_id: int
) -> JobBoardConnection:
    """Return one of the user's connections.

    Args:
        db: Async database session.
        user_id: The owning user.
        connection_id: The connection to return.

    Returns:
        The connection.

    Raises:
        ConnectionNotFoundError: If it does not exist for this user.
    """
    result = await db.execute(
        select(JobBoardConnection).where(
            JobBoardConnection.id == connection_id,
            JobBoardConnection.user_id == user_id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise ConnectionNotFoundError
    return connection
