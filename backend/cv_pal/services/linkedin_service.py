"""Import and review the user's LinkedIn profile.

**CV Pal never fetches linkedin.com.** Automated access is against LinkedIn's terms and
the account it would endanger is the user's own — a restricted account costs them the
professional network their job search runs on. So the profile arrives as a document they
exported themselves, by one of the routes in `docs/linkedin-import.md`.

The snapshot is deliberately *not* promoted into the career profile. Extraction from a
document nobody verified is guesswork, and the career profile is what CV generation is
grounded in; the user moves records across through the ordinary profile endpoints, the
same contract `extract_from_cv` uses. That is what keeps *never fabricate experience*
true of an importer that is necessarily inferring.
"""

import tempfile
from datetime import date
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.analysis.extraction import ExtractedEntry
from cv_pal.analysis.linkedin import (
    LinkedInReview,
    LinkedInSnapshot,
    looks_like_linkedin,
    parse_profile,
    review,
)
from cv_pal.analysis.linkedin_export import parse_export
from cv_pal.constants import (
    DEFAULT_ERROR_FILE_TOO_LARGE,
    DEFAULT_ERROR_FILE_TYPE_NOT_ALLOWED,
    DEFAULT_LINKEDIN_EXTENSIONS,
    DEFAULT_LINKEDIN_MAGIC_BYTES,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_UPLOAD_CHUNK_SIZE,
    LinkedInSource,
)
from cv_pal.exceptions import (
    LinkedInExportEmptyError,
    LinkedInProfileNotFoundError,
    LinkedInUnreadableError,
    ValidationError,
)
from cv_pal.models import LinkedInProfile
from cv_pal.parsing import extract_cv_text
from cv_pal.services.profile_service import get_or_create_goals, get_or_create_profile
from cv_pal.storage import delete_file


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Read an upload into memory, enforcing the type and size rules.

    Held in memory rather than streamed to the upload directory: unlike a CV, a LinkedIn
    snapshot is parsed once and stored as structured records, so keeping the file would
    leave a sensitive document on disk that nothing ever reads again.

    Args:
        file: The uploaded file.

    Returns:
        The lowercased extension and the file's bytes.

    Raises:
        ValidationError: If the extension, content or size is not acceptable.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in DEFAULT_LINKEDIN_EXTENSIONS:
        allowed = ", ".join(sorted(DEFAULT_LINKEDIN_EXTENSIONS))
        raise ValidationError(
            DEFAULT_ERROR_FILE_TYPE_NOT_ALLOWED.format(allowed=allowed)
        )

    chunks: list[bytes] = []
    written = 0
    while chunk := await file.read(DEFAULT_UPLOAD_CHUNK_SIZE):
        written += len(chunk)
        if written > DEFAULT_MAX_FILE_SIZE:
            size_mb = DEFAULT_MAX_FILE_SIZE // (1024 * 1024)
            raise ValidationError(DEFAULT_ERROR_FILE_TOO_LARGE.format(size_mb=size_mb))
        chunks.append(chunk)

    data = b"".join(chunks)
    expected = DEFAULT_LINKEDIN_MAGIC_BYTES[suffix]
    if not data.startswith(expected):
        raise LinkedInUnreadableError

    return suffix, data


async def _snapshot_from_pdf(data: bytes) -> LinkedInSnapshot:
    """Parse a LinkedIn PDF, whichever of the two PDF routes produced it.

    The text extractor works on a path, so the bytes go to a temporary file that is
    removed as soon as the text is out — the document itself is never kept.

    Args:
        data: The PDF bytes.

    Returns:
        The parsed snapshot.

    Raises:
        LinkedInUnreadableError: If the document does not read as a LinkedIn profile.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(data)
        path = Path(handle.name)
    try:
        text = await extract_cv_text(path)
    finally:
        await delete_file(path)

    if not looks_like_linkedin(text):
        raise LinkedInUnreadableError
    return parse_profile(text, source=LinkedInSource.PDF)


def _snapshot_from_export(data: bytes) -> LinkedInSnapshot:
    """Parse a LinkedIn data-export archive.

    Args:
        data: The ZIP bytes.

    Returns:
        The parsed snapshot.

    Raises:
        LinkedInExportEmptyError: If the archive holds none of the profile files.
        LinkedInUnreadableError: If the archive cannot be read at all.
    """
    try:
        snapshot = parse_export(data)
    except ValueError as exc:
        raise LinkedInUnreadableError from exc

    if snapshot.is_empty:
        raise LinkedInExportEmptyError
    return snapshot


def _entry_to_json(entry: ExtractedEntry) -> dict[str, str | None]:
    """Flatten a parsed entry for JSON storage.

    Args:
        entry: The entry.

    Returns:
        A JSON-safe mapping with ISO dates.
    """
    return {
        "organisation": entry.organisation,
        "title": entry.title,
        "location": entry.location,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "description": entry.description,
    }


async def import_profile(
    db: AsyncSession,
    *,
    user_id: int,
    file: UploadFile | None = None,
    text: str | None = None,
) -> LinkedInProfile:
    """Import a LinkedIn profile from a file or pasted text, replacing any previous one.

    Replaced rather than versioned: this is a photograph of a document, and keeping
    several would raise the question of which one the review speaks for.

    Args:
        db: Async database session.
        user_id: The owning user.
        file: An uploaded PDF or data-export ZIP, when that is the route used.
        text: Pasted profile text, when that is the route used.

    Returns:
        The stored snapshot.

    Raises:
        ValidationError: If neither a file nor text was supplied.
        LinkedInUnreadableError: If the document does not read as a LinkedIn profile.
        LinkedInExportEmptyError: If an archive carried no profile files.
    """
    if file is not None:
        suffix, data = await _read_upload(file)
        snapshot = (
            await _snapshot_from_pdf(data)
            if suffix == ".pdf"
            else _snapshot_from_export(data)
        )
    elif text is not None:
        # A paste is not held to the fingerprint check: the user has told us what it is
        # by choosing this route, and a copied profile carries no sidebar to detect.
        snapshot = parse_profile(text, source=LinkedInSource.PASTE)
        if snapshot.is_empty:
            raise LinkedInUnreadableError
    else:  # pragma: no cover - the router validates this first
        raise ValidationError

    result = await db.execute(
        select(LinkedInProfile).where(LinkedInProfile.user_id == user_id)
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        # The JSON column defaults land on insert, and the merge below reads them
        # before the flush.
        stored = LinkedInProfile(
            user_id=user_id,
            source=snapshot.source.value,
            positions=[],
            educations=[],
            skills=[],
            sections_found=[],
            field_sources={},
            raw_text="",
        )
        db.add(stored)

    _merge(stored, snapshot)
    await db.commit()
    await db.refresh(stored)
    return stored


def _wins(stored: LinkedInProfile, group: str, source: LinkedInSource) -> bool:
    """Decide whether an incoming import may replace a stored field group.

    The routes differ in how much they actually carry, so "last import wins" loses data:
    a profile PDF lists only the **top three skills** and no role descriptions at all,
    so importing one after the official archive would silently throw away the full
    skill list. An import therefore only takes a group when it is at least as exact as
    whatever supplied it last — which also lets a user import the PDF for the quick
    review and add the archive three days later without redoing anything.

    Args:
        stored: The existing snapshot.
        group: The field group being merged.
        source: The incoming import's route.

    Returns:
        True when the incoming data should be kept.
    """
    previous = stored.field_sources.get(group)
    if previous is None:
        return True
    return source.precision >= LinkedInSource(previous).precision


def _merge(stored: LinkedInProfile, snapshot: LinkedInSnapshot) -> None:
    """Fold a freshly parsed snapshot into the stored one, per field group.

    A group is only touched when the import actually carried it, so a route that omits
    a section leaves what is already there alone rather than blanking it.

    Args:
        stored: The row to update in place.
        snapshot: The newly parsed profile.
    """
    source = snapshot.source
    sources = dict(stored.field_sources)

    def take(group: str, present: bool) -> bool:
        if not present or not _wins(stored, group, source):
            return False
        sources[group] = source.value
        return True

    if take("identity", bool(snapshot.name or snapshot.headline)):
        stored.full_name = snapshot.name or stored.full_name
        stored.headline = snapshot.headline or stored.headline
    if take("about", bool(snapshot.about)):
        stored.about = snapshot.about
    if take("positions", bool(snapshot.positions)):
        stored.positions = [_entry_to_json(entry) for entry in snapshot.positions]
    if take("educations", bool(snapshot.educations)):
        stored.educations = [_entry_to_json(entry) for entry in snapshot.educations]
    if take("skills", bool(snapshot.skills)):
        stored.skills = list(snapshot.skills)

    if snapshot.profile_url:
        stored.profile_url = snapshot.profile_url
    if snapshot.text:
        stored.raw_text = snapshot.text

    stored.sections_found = sorted(
        set(stored.sections_found) | set(snapshot.sections_found)
    )
    stored.field_sources = sources
    # The row records the most exact route that has contributed, since that is what
    # decides how much the review can honestly claim.
    stored.source = max(
        (LinkedInSource(value) for value in sources.values()),
        key=lambda item: item.precision,
        default=source,
    ).value


async def get_profile(db: AsyncSession, *, user_id: int) -> LinkedInProfile:
    """Return the user's imported snapshot.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The stored snapshot.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    result = await db.execute(
        select(LinkedInProfile).where(LinkedInProfile.user_id == user_id)
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        raise LinkedInProfileNotFoundError
    return stored


async def delete_profile(db: AsyncSession, *, user_id: int) -> None:
    """Delete the user's imported snapshot.

    A LinkedIn profile is a sensitive document, so removing it is a first-class action
    rather than something only account deletion can do.

    Args:
        db: Async database session.
        user_id: The owning user.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    stored = await get_profile(db, user_id=user_id)
    await db.delete(stored)
    await db.commit()


def _stored_to_snapshot(stored: LinkedInProfile) -> LinkedInSnapshot:
    """Rebuild the parsed snapshot from its stored form.

    Args:
        stored: The stored row.

    Returns:
        The snapshot the review runs over.
    """
    return LinkedInSnapshot(
        source=LinkedInSource(stored.source),
        profile_url=stored.profile_url,
        name=stored.full_name,
        headline=stored.headline,
        about=stored.about,
        positions=tuple(_json_to_entry(item) for item in stored.positions),
        educations=tuple(_json_to_entry(item) for item in stored.educations),
        skills=tuple(stored.skills),
        sections_found=tuple(stored.sections_found),
        text=stored.raw_text,
    )


def _json_to_entry(item: dict[str, str | None]) -> ExtractedEntry:
    """Rebuild a parsed entry from its stored form.

    Args:
        item: One stored entry.

    Returns:
        The entry.
    """

    def as_date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None

    return ExtractedEntry(
        organisation=item.get("organisation") or "",
        title=item.get("title") or "",
        location=item.get("location"),
        start_date=as_date(item.get("start_date")),
        end_date=as_date(item.get("end_date")),
        description=item.get("description"),
    )


async def review_profile(db: AsyncSession, *, user_id: int) -> LinkedInReview:
    """Review the imported profile against the career profile and the user's goals.

    Recomputed on every call rather than stored: the verdict depends on the career
    profile and the target roles, both of which change more often than the snapshot, and
    a cached review would quietly go stale against the record it is comparing.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The review.

    Raises:
        LinkedInProfileNotFoundError: If nothing has been imported yet.
    """
    stored = await get_profile(db, user_id=user_id)
    profile = await get_or_create_profile(db, user_id=user_id)
    goals = await get_or_create_goals(db, user_id=user_id)

    experiences = [
        ExtractedEntry(
            organisation=experience.organisation,
            title=experience.title,
            location=experience.location,
            start_date=experience.start_date,
            end_date=experience.end_date,
            description=experience.description,
        )
        for experience in profile.experiences
    ]

    return review(
        _stored_to_snapshot(stored),
        experiences=experiences,
        target_roles=list(goals.target_roles),
    )
