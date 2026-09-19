"""Read LinkedIn's official data export archive.

Option 4 in `docs/linkedin-import.md`: the user requests their data, LinkedIn takes up
to 72 hours, and what arrives is a ZIP of CSVs rather than page text. It is the richest
route — **dates, titles and skills arrive exact rather than inferred** — and useless as
a first-run experience, which is why the PDF routes exist alongside it.

Parsing it is a different job from parsing a PDF, not a harder one: the fields are
already structured, so nothing here guesses. Anything the archive does not state stays
None rather than being reconstructed.

Everything runs over the archive in memory and never executes or extracts anything to
disk, so a hostile ZIP is a parse failure and not a path traversal.
"""

import csv
import io
import zipfile
from datetime import date

from cv_pal.analysis.extraction import ExtractedEntry
from cv_pal.analysis.keywords import canonical
from cv_pal.analysis.linkedin import LinkedInSnapshot
from cv_pal.constants import LinkedInSource

# Consistently named but nested differently per archive type, so matched on basename.
_PROFILE_FILE = "profile.csv"
_POSITIONS_FILE = "positions.csv"
_EDUCATION_FILE = "education.csv"
_SKILLS_FILE = "skills.csv"

# The archive is a handful of small CSVs; anything past this is a ZIP bomb.
_MAX_MEMBER_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_BYTES = 32 * 1024 * 1024

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Index the archive's useful members by lowercased basename.

    Args:
        archive: The opened archive.

    Returns:
        Basename to member info, for the profile files only.
    """
    wanted = {_PROFILE_FILE, _POSITIONS_FILE, _EDUCATION_FILE, _SKILLS_FILE}
    found: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.rsplit("/", 1)[-1].lower()
        if name in wanted:
            found[name] = info
    return found


def _read_rows(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> list[dict[str, str]]:
    """Read one CSV member into rows.

    Args:
        archive: The opened archive.
        info: The member to read.

    Returns:
        The rows, with whitespace-stripped keys.

    Raises:
        ValueError: If the member is larger than the size guard allows.
    """
    if info.file_size > _MAX_MEMBER_BYTES:
        raise ValueError(f"{info.filename} is too large to be a profile export")

    with archive.open(info) as handle:
        raw = handle.read(_MAX_MEMBER_BYTES + 1)
    if len(raw) > _MAX_MEMBER_BYTES:
        raise ValueError(f"{info.filename} is too large to be a profile export")

    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append(
            {
                (key or "").strip(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
        )
    return rows


def _parse_month_year(value: str) -> date | None:
    """Parse the ``Mon YYYY`` and ``YYYY`` forms LinkedIn writes into its CSVs.

    Args:
        value: The cell contents.

    Returns:
        The first of the month, or None when the cell is blank or unrecognised.
    """
    parts = value.replace(",", " ").split()
    if not parts:
        return None

    year: int | None = None
    month = 1
    for part in parts:
        key = part[:3].lower()
        if key in _MONTHS:
            month = _MONTHS[key]
        elif part.isdigit() and len(part) == 4:
            year = int(part)

    if year is None:
        return None
    try:
        return date(year, month, 1)
    except ValueError:  # pragma: no cover - month is bounded by the table above
        return None


def _first(row: dict[str, str], *names: str) -> str:
    """Return the first non-empty value among several possible column names.

    LinkedIn has renamed these columns across export versions, so each field is looked
    up under every spelling it has shipped with.

    Args:
        row: One CSV row.
        *names: Column names to try, in order.

    Returns:
        The value, or an empty string when none of the columns held one.
    """
    for name in names:
        value = row.get(name, "")
        if value:
            return value
    return ""


def _positions(rows: list[dict[str, str]]) -> tuple[ExtractedEntry, ...]:
    """Build roles from ``Positions.csv``.

    Args:
        rows: The parsed rows.

    Returns:
        The roles, skipping rows with no employer.
    """
    entries: list[ExtractedEntry] = []
    for row in rows:
        organisation = _first(row, "Company Name", "Company")
        if not organisation:
            continue
        entries.append(
            ExtractedEntry(
                organisation=organisation,
                title=_first(row, "Title", "Position") or organisation,
                location=_first(row, "Location") or None,
                start_date=_parse_month_year(_first(row, "Started On", "Start Date")),
                end_date=_parse_month_year(_first(row, "Finished On", "End Date")),
                description=_first(row, "Description") or None,
            )
        )
    return tuple(entries)


def _educations(rows: list[dict[str, str]]) -> tuple[ExtractedEntry, ...]:
    """Build qualifications from ``Education.csv``.

    Args:
        rows: The parsed rows.

    Returns:
        The qualifications, skipping rows with no institution.
    """
    entries: list[ExtractedEntry] = []
    for row in rows:
        organisation = _first(row, "School Name", "School")
        if not organisation:
            continue
        degree = _first(row, "Degree Name", "Degree")
        study = _first(row, "Field Of Study", "Field of Study")
        title = " ".join(part for part in (degree, study) if part) or organisation
        entries.append(
            ExtractedEntry(
                organisation=organisation,
                title=title,
                start_date=_parse_month_year(_first(row, "Start Date", "Started On")),
                end_date=_parse_month_year(_first(row, "End Date", "Finished On")),
                description=_first(row, "Notes", "Activities") or None,
            )
        )
    return tuple(entries)


def _skills(rows: list[dict[str, str]]) -> tuple[str, ...]:
    """Build the skill list from ``Skills.csv``.

    Args:
        rows: The parsed rows.

    Returns:
        Skill names, deduplicated on their canonical form.
    """
    seen: set[str] = set()
    skills: list[str] = []
    for row in rows:
        name = _first(row, "Name", "Skill")
        if not name:
            continue
        key = canonical(name)
        if key in seen:
            continue
        seen.add(key)
        skills.append(name)
    return tuple(skills)


def parse_export(data: bytes) -> LinkedInSnapshot:
    """Parse a LinkedIn data-export archive into a snapshot.

    Args:
        data: The raw ZIP bytes.

    Returns:
        The snapshot. Empty when the archive holds none of the profile files, which the
        caller reports rather than treating as a parse failure — selecting the wrong
        files when requesting the export is an easy mistake to make.

    Raises:
        ValueError: If the bytes are not a readable ZIP, or a member is implausibly
            large for a profile export.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("That file is not a readable ZIP archive") from exc

    with archive:
        members = _members(archive)
        if not members:
            return LinkedInSnapshot(source=LinkedInSource.EXPORT)

        if sum(info.file_size for info in members.values()) > _MAX_TOTAL_BYTES:
            raise ValueError("That archive is too large to be a profile export")

        profile_rows = (
            _read_rows(archive, members[_PROFILE_FILE])
            if _PROFILE_FILE in members
            else []
        )
        position_rows = (
            _read_rows(archive, members[_POSITIONS_FILE])
            if _POSITIONS_FILE in members
            else []
        )
        education_rows = (
            _read_rows(archive, members[_EDUCATION_FILE])
            if _EDUCATION_FILE in members
            else []
        )
        skill_rows = (
            _read_rows(archive, members[_SKILLS_FILE])
            if _SKILLS_FILE in members
            else []
        )

    profile = profile_rows[0] if profile_rows else {}
    name = " ".join(
        part
        for part in (_first(profile, "First Name"), _first(profile, "Last Name"))
        if part
    )

    # Lets the review tell "you have no About section" from "you did not export it".
    sections = tuple(
        key
        for key, present in (
            ("about", bool(_first(profile, "Summary"))),
            ("experience", bool(position_rows)),
            ("education", bool(education_rows)),
            ("skills", bool(skill_rows)),
        )
        if present
    )

    return LinkedInSnapshot(
        source=LinkedInSource.EXPORT,
        profile_url=None,
        name=name or None,
        headline=_first(profile, "Headline") or None,
        about=_first(profile, "Summary") or None,
        positions=_positions(position_rows),
        educations=_educations(education_rows),
        skills=_skills(skill_rows),
        sections_found=sections,
        # Not one document, so there is no page text — the parsed records are it.
        text="",
    )


__all__ = ["parse_export"]
