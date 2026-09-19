"""Deterministic extraction of structured records from CV text.

No language model. This exists so that importing a CV into the career profile works on
a fresh install with no API key and no Ollama, and so the expensive, non-reproducible
path is an *enricher* rather than the thing everything else depends on.

**The output is a proposal, never a write.** Nothing here persists anything: the caller
gets candidate records and the user confirms them through the ordinary profile
endpoints. That is what keeps *never fabricate experience* true of an extractor that is,
by nature, guessing: a wrong guess costs one rejected suggestion, not a false claim.

Designed against a real two-column CV, which is why it reflows before it parses: PDF
text extraction on a two-column layout emits a date column as one word per line
(``AUG``/``2018``/``-``/``FEB``/``2019``), so matching line by line finds
nothing. 74% of the lines in the document this was built against hold one word.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from cv_pal.analysis.keywords import canonical
from cv_pal.analysis.vocabulary import (
    EDUCATION_MARKERS,
    EXPECTED_SECTIONS,
    KNOWN_TERMS,
    SKILL_ALIASES,
    SUMMARY_HEADINGS,
)
from cv_pal.constants import (
    DEFAULT_HEADLINE_MAX_LENGTH,
    DEFAULT_LOCATION_MAX_LENGTH,
    DEFAULT_PHONE_MAX_LENGTH,
    DEFAULT_SUMMARY_MAX_LENGTH,
)

# Extraction reads one section the parseability checker deliberately does not require.
_SECTIONS = {**EXPECTED_SECTIONS, "summary": SUMMARY_HEADINGS}

_WHITESPACE = re.compile(r"\s+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", re.IGNORECASE
)
_WEBSITE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com/[\w-]+|[\w-]+\.(?:dev|io|me|com)/?[\w-]*)",
    re.IGNORECASE,
)
# The same pattern the parseability check looks for, so the two agree about what counts
# as a phone number on a CV.
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# "AUG 2018 - FEB 2019", "2021 to Present", "Jul 2016 to Dec 2018". Matched against the
# reflowed text, so a two-column layout's fragments are already rejoined.
_DATE_RANGE = re.compile(
    r"\b(?:(?P<m1>[a-z]{3,9})\s+)?(?P<y1>(?:19|20)\d{2})\s*"
    r"(?:[-\u2013\u2014]|\bto\b)\s*"
    r"(?:(?P<present>present|current|now|ongoing)"
    r"|(?:(?P<m2>[a-z]{3,9})\s+)?(?P<y2>(?:19|20)\d{2}))",
    re.IGNORECASE,
)

# "Employer, City — Role". The em dash is a strong template convention and, unlike
# indentation or font weight, it survives text extraction.
_ENTRY = re.compile(
    r"^(?P<left>[^\n]{2,90}?)\s+[\u2014\u2013]\s+(?P<right>[^\n]{2,90})$"
)

_HEADING_MAX_WORDS = 4
_SKILL_SEPARATORS = re.compile(r"[,;•·|]|\s{2,}|\band\b", re.IGNORECASE)

# How far into the document a header can reasonably run, and the shapes its lines take.
_HEADER_LINES = 8
_HEADLINE_MAX_WORDS = 10
_PLACE_MAX_WORDS = 5
_DOCUMENT_TITLES = frozenset({"curriculum vitae", "cv", "resume", "résumé"})
# A phone number is a header fact. Searching the whole document finds date ranges.
_PHONE_SEARCH_LINES = 16
_PHONE_MIN_DIGITS = 9
# The separators a header puts between its fields, left behind once the contact details
# they divide have been removed.
_HEADER_TRIM = " |\u00b7\u2022-\u2013\u2014"


@dataclass(frozen=True, slots=True)
class ExtractedContact:
    """Contact details found anywhere in the document."""

    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedEntry:
    """A dated entry — a role or a course — as read from the document.

    Attributes:
        organisation: The employer or institution.
        title: The role or qualification.
        location: Where it was, when the entry names it.
        start_date: First of the starting month, or the year when no month was given.
        end_date: None when the entry reads as current.
        description: The prose that followed the heading, trimmed.
    """

    organisation: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedProfile:
    """Everything the deterministic pass could find. All of it is a proposal.

    Attributes:
        contact: Links and the email, found anywhere in the document.
        headline: The title line under the name, when the header carries one.
        summary: The opening paragraph, when the CV labelled one.
        location: Where the header says the writer is.
        experiences: Dated roles.
        educations: Dated study.
        skills: Recognised skill names from the skills section.
    """

    contact: ExtractedContact = field(default_factory=ExtractedContact)
    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    experiences: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    educations: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)


def _reflow(text: str) -> list[str]:
    """Rejoin the fragments a multi-column PDF produces, without losing real breaks.

    A line holding a single short token is almost never a real line — it is a column
    cell. Consecutive ones are joined so that a date split over five lines becomes one
    string again. A line that already carries several words is left alone.

    Args:
        text: The extracted CV text.

    Returns:
        Logical lines, whitespace collapsed.
    """
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    merged: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if len(line.split()) <= 2 and not _is_heading(line):
            buffer.append(line)
            continue
        if buffer:
            merged.append(" ".join(buffer))
            buffer = []
        merged.append(line)
    if buffer:
        merged.append(" ".join(buffer))
    return merged


def _is_heading(line: str) -> bool:
    """Report whether a line looks like a section heading.

    Args:
        line: A reflowed line.

    Returns:
        True for the short, unpunctuated, known-heading lines CVs use.
    """
    words = line.split()
    if not words or len(words) > _HEADING_MAX_WORDS or line.endswith((".", ",")):
        return False
    return _section_for(line) is not None


def _section_for(line: str) -> str | None:
    """Return the section a heading introduces, or None.

    Args:
        line: A candidate heading.

    Returns:
        The section key from ``EXPECTED_SECTIONS``, or None.
    """
    lowered = line.casefold().strip(" :")
    for name, headings in _SECTIONS.items():
        if any(
            lowered == heading or lowered.startswith(heading) for heading in headings
        ):
            return name
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Group reflowed lines under the heading that precedes them.

    Args:
        lines: Reflowed lines.

    Returns:
        Section key to its lines. Text before the first heading is under ``header``.
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        section = _section_for(line) if _is_heading(line) else None
        if section is not None:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _parse_dates(text: str) -> tuple[date | None, date | None]:
    """Read the first date range in a block of text.

    Args:
        text: An entry's text.

    Returns:
        ``(start, end)``. ``end`` is None when the entry reads as current. Both are
        None when no range was found — an entry with unreadable dates is still worth
        proposing, since the user can fill them in.
    """
    match = _DATE_RANGE.search(text)
    if match is None:
        return None, None

    start = _as_date(match.group("m1"), match.group("y1"))
    if match.group("present"):
        return start, None
    return start, _as_date(match.group("m2"), match.group("y2"), end_of_range=True)


def find_date_range(text: str) -> tuple[date | None, date | None] | None:
    """Read the first date range in a line, distinguishing "none" from "unreadable".

    `_parse_dates` answers ``(None, None)`` both when a line has no dates and when it
    has dates that would not parse. The LinkedIn parser cuts entries at date lines, so
    it needs to know which of the two happened.

    Args:
        text: A single line or block of text.

    Returns:
        ``(start, end)`` when the text holds a range, or None when it holds none.
    """
    if _DATE_RANGE.search(text) is None:
        return None
    return _parse_dates(text)


def _as_date(
    month: str | None, year: str, *, end_of_range: bool = False
) -> date | None:
    """Build a date from a month name and a year.

    Args:
        month: A month name or abbreviation, if the entry gave one.
        year: A four-digit year.
        end_of_range: Whether this is the closing date, which defaults to December
            rather than January so a year-only range spans the whole year.

    Returns:
        The first of the month, or None if the year is unusable.
    """
    number = _MONTHS.get(month.casefold()) if month else None
    if number is None:
        number = 12 if end_of_range else 1
    try:
        return date(int(year), number, 1)
    except ValueError:  # pragma: no cover - the regex already bounds the year
        return None


def _is_education(entry: ExtractedEntry) -> bool:
    """Decide whether a dated entry is study rather than work.

    Judged from the entry's own words — "University", "BSc", "School" — rather than the
    heading above it, because a two-column layout interleaves the sidebar into the
    reading order and puts entries under whatever heading happens to precede them.

    Args:
        entry: A parsed entry.

    Returns:
        True when the organisation or title names an institution or a qualification.
    """
    words = f"{entry.organisation} {entry.title}".casefold().replace("(", " ").split()
    return any(word.strip(".,-") in EDUCATION_MARKERS for word in words)


def _entries(lines: list[str]) -> tuple[ExtractedEntry, ...]:
    """Read dated entries from a run of lines.

    Anchors on the ``Organisation, Location - Title`` heading and treats everything
    up to the next anchor as that entry's, which is what makes this tolerant of a
    scrambled reading order: the dates and the prose need only be *near* their
    heading, not on the same line.

    Args:
        lines: The section's reflowed lines.

    Returns:
        The entries found, in document order.
    """
    anchors = [index for index, line in enumerate(lines) if _ENTRY.match(line)]

    found: list[ExtractedEntry] = []
    for position, index in enumerate(anchors):
        match = _ENTRY.match(lines[index])
        if match is None:  # pragma: no cover - anchors were built from the same match
            continue

        stop = anchors[position + 1] if position + 1 < len(anchors) else len(lines)
        body = " ".join(lines[index + 1 : stop])
        start, end = _parse_dates(body)

        left = match.group("left").strip()
        organisation, _, location = left.rpartition(",")
        if not organisation:
            organisation, location = left, ""

        description = _DATE_RANGE.sub("", body).strip(" -\u2013\u2014")
        found.append(
            ExtractedEntry(
                organisation=organisation.strip(),
                title=match.group("right").strip(),
                location=location.strip() or None,
                start_date=start,
                end_date=end,
                description=description or None,
            )
        )
    return tuple(found)


def _skills(lines: list[str]) -> tuple[str, ...]:
    """Read skills from the skills section.

    Only terms the vocabulary recognises are proposed. A skills section is a list of
    comma-separated fragments with no reliable structure, so accepting everything would
    fill the profile with sentence fragments the user then has to delete one by one.

    Args:
        lines: The section's reflowed lines.

    Returns:
        Distinct skill names, in the order they appeared.
    """
    seen: list[str] = []
    for line in lines:
        for fragment in _SKILL_SEPARATORS.split(line):
            name = fragment.strip(" .:-\u2013\u2014()")
            if not name or len(name.split()) > 3:
                continue
            resolved = canonical(name)
            known = resolved in KNOWN_TERMS or resolved in SKILL_ALIASES.values()
            if known and resolved not in seen:
                seen.append(resolved)
    return tuple(seen)


def _phone(raw: str) -> str | None:
    """Find a phone number in the header, if the document carries one.

    Confined to the header and held to a minimum digit count, unlike the parseability
    check which only asks whether the document contains anything phone-shaped. That
    pattern happily matches a date range, and a proposal is worth less than nothing if
    it offers "2018 - 2021" as somebody's phone number.

    Args:
        raw: The whole CV text, line breaks intact.

    Returns:
        The number as written, or None.
    """
    header = "\n".join(raw.splitlines()[:_PHONE_SEARCH_LINES])
    for match in _PHONE.finditer(header):
        found = match.group(0).strip()
        if sum(character.isdigit() for character in found) >= _PHONE_MIN_DIGITS:
            return found[:DEFAULT_PHONE_MAX_LENGTH]
    return None


def _contact(text: str, raw: str) -> ExtractedContact:
    """Find contact details anywhere in the document.

    Args:
        text: The whole CV text, whitespace collapsed.
        raw: The same text with its line breaks, for the header-only phone search.

    Returns:
        Whatever was found.
    """
    email = _EMAIL.search(text)
    linkedin = _LINKEDIN.search(text)

    # Emails removed first, or "name@gmail.com" yields "gmail.com" as their website.
    without_emails = _EMAIL.sub(" ", text)

    website: str | None = None
    for candidate in _WEBSITE.finditer(without_emails):
        value = candidate.group(0)
        # The LinkedIn URL matches the generic pattern too; it has its own field.
        if "linkedin.com" not in value.lower():
            website = value
            break

    return ExtractedContact(
        email=email.group(0) if email else None,
        phone=_phone(raw),
        linkedin_url=linkedin.group(0) if linkedin else None,
        website_url=website,
    )


def _summary(lines: list[str]) -> str | None:
    """Read the opening paragraph out of whichever section held it.

    Args:
        lines: The summary section's reflowed lines.

    Returns:
        The paragraph as one string, or None when the CV labelled no summary. Long
        sections are cut at the column's limit rather than rejected — a summary that
        runs long is still the right starting point, and the user edits it before it
        is saved.
    """
    text = " ".join(lines).strip()
    if not text:
        return None
    return text[:DEFAULT_SUMMARY_MAX_LENGTH].strip()


def _looks_like_a_name(line: str) -> bool:
    """Report whether a header line reads as a person's name.

    Used only to know which line to skip: the line under the name is the headline, and
    without this the name itself would be proposed as one.

    Args:
        line: A header line, contact details already removed.

    Returns:
        True for two to four capitalised words with no digits.
    """
    words = line.split()
    if not 2 <= len(words) <= 4 or any(char.isdigit() for char in line):
        return False
    return all(word[:1].isupper() for word in words)


def _looks_like_a_place(line: str) -> bool:
    """Report whether a header line reads as ``City, Country``.

    Args:
        line: A header line, contact details already removed.

    Returns:
        True for a short comma-separated place with no digits.
    """
    if "," not in line or any(char.isdigit() for char in line):
        return False
    parts = [part.strip() for part in line.split(",")]
    return (
        len(parts) == 2
        and all(parts)
        and len(line.split()) <= _PLACE_MAX_WORDS
        and line[:1].isupper()
    )


def _header_facts(text: str) -> tuple[str | None, str | None]:
    """Read the headline and the location from the top of the document.

    Deliberately reads the *raw* lines rather than the reflowed ones: reflowing joins
    consecutive short lines, and a header is almost entirely short lines, so the name,
    the title and the city arrive merged into a single unusable string.

    The shape it expects is the one nearly every CV opens with — a name, a title, then
    contact details. A wrong guess is the cheapest failure in this module: the caller
    shows both values for confirmation and stores neither until the user says so.

    Args:
        text: The whole CV text.

    Returns:
        ``(headline, location)``, either of which may be None.
    """
    candidates: list[str] = []
    for raw in text.splitlines():
        # Contact details are the noise in a header; without them the remaining lines
        # are the name, the title and the place, in that order.
        line = _WEBSITE.sub(" ", _LINKEDIN.sub(" ", _EMAIL.sub(" ", raw)))
        line = _WHITESPACE.sub(" ", line).strip(_HEADER_TRIM)
        # The header ends at the first section heading, whatever the line count says.
        # Without this the scan runs into the first role and proposes it as a headline.
        if _is_heading(line):
            break
        if line:
            candidates.append(line)
        if len(candidates) >= _HEADER_LINES:
            break

    headline: str | None = None
    location: str | None = None
    named = False
    for line in candidates:
        if location is None and _looks_like_a_place(line):
            location = line[:DEFAULT_LOCATION_MAX_LENGTH]
            continue
        if line.casefold() in _DOCUMENT_TITLES:
            continue
        # The name is skipped once, wherever it turns up: a "Curriculum Vitae" title
        # above it would otherwise make the name itself look like the headline.
        if not named and _looks_like_a_name(line):
            named = True
            continue
        if (
            headline is None
            and 1 < len(line.split()) <= _HEADLINE_MAX_WORDS
            and not line.endswith(".")
        ):
            headline = line[:DEFAULT_HEADLINE_MAX_LENGTH]

    return headline, location


def extract_profile(cv_text: str) -> ExtractedProfile:
    """Read structured records out of a CV.

    Args:
        cv_text: Text extracted from an uploaded CV.

    Returns:
        A proposal for the user to confirm. Nothing is persisted, and an empty result is
        a normal outcome for a CV whose layout does not survive extraction.
    """
    lines = _reflow(cv_text)
    sections = _split_sections(lines)
    flat = _WHITESPACE.sub(" ", cv_text)

    # Gathered whole-document then classified: on a multi-column CV the headings
    # cannot be trusted to bound sections. See `_is_education`.
    entries = _entries(lines)
    headline, location = _header_facts(cv_text)

    return ExtractedProfile(
        contact=_contact(flat, cv_text),
        headline=headline,
        summary=_summary(sections.get("summary", [])),
        location=location,
        experiences=tuple(e for e in entries if not _is_education(e)),
        educations=tuple(e for e in entries if _is_education(e)),
        skills=_skills(sections.get("skills", [])),
    )
