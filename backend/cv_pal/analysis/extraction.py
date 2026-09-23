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
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from cv_pal.analysis.keywords import canonical
from cv_pal.analysis.vocabulary import (
    EDUCATION_MARKERS,
    EXPECTED_SECTIONS,
    KNOWN_TERMS,
    ORGANISATION_MARKERS,
    OTHER_HEADINGS,
    ROLE_MARKERS,
    SKILL_ALIASES,
    SUMMARY_HEADINGS,
)
from cv_pal.constants import (
    DEFAULT_HEADLINE_MAX_LENGTH,
    DEFAULT_LOCATION_MAX_LENGTH,
    DEFAULT_PHONE_MAX_LENGTH,
    DEFAULT_SUMMARY_MAX_LENGTH,
    LanguageLevel,
)

# Extraction reads one section the parseability checker deliberately does not require.
_SECTIONS = {
    **EXPECTED_SECTIONS,
    "summary": SUMMARY_HEADINGS,
    "other": OTHER_HEADINGS,
}

_WHITESPACE = re.compile(r"\s+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", re.IGNORECASE
)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+", re.IGNORECASE)
_WEBSITE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com/[\w-]+|[\w-]+\.(?:dev|io|me|com)/?[\w-]*)",
    re.IGNORECASE,
)
# The same pattern the parseability check looks for, so the two agree about what counts
# as a phone number on a CV.
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}")

# Only these are read as months, so a place name before a year ("Bristol 2005 - 2008")
# is never taken for one.
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

_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))


def _date_point(n: int) -> str:
    """Build the pattern for one end of a range: ``Aug 2018``, ``08/2018``, ``2018``.

    Args:
        n: 1 or 2, suffixed to the group names.

    Returns:
        The pattern, with groups ``m<n>`` (month name), ``n<n>`` (month number) and
        ``y<n>`` (year).
    """
    return (
        rf"(?:(?P<m{n}>{_MONTH_NAMES})\b\.?[\s'\u2019/-]*"
        rf"|(?P<n{n}>0?[1-9]|1[0-2])\s*[/.]\s*)?"
        rf"(?P<y{n}>(?:19|20)\d{{2}})\b"
    )


# "AUG 2018 - FEB 2019", "2021 to Present", "05/2019 - 01/2021", "Jan. 2021 - now".
# Matched against the reflowed text, so a two-column layout's fragments are already
# rejoined.
_DATE_RANGE = re.compile(
    rf"\b{_date_point(1)}\s*"
    r"(?:[-\u2010-\u2015\u2212]+|\b(?:to|until|till|through)\b)\s*"
    rf"(?:(?P<present>present|current|now|ongoing|today)\b|{_date_point(2)})",
    re.IGNORECASE,
)

# "Employer, City — Role" with no dates on the line; they follow on the next one. The
# em dash is a strong template convention and, unlike indentation or font weight, it
# survives text extraction.
_ENTRY = re.compile(
    r"^(?P<left>[^\n]{2,90}?)\s+[\u2014\u2013]\s+(?P<right>[^\n]{2,90})$"
)

# What a CV puts between the parts of an entry heading, strongest first. Commas are
# tried only when none of these split it, since they also sit inside names.
_STRONG_SEPARATORS = re.compile(
    r"\s+[\u2014\u2013|\u00b7\u2022-]\s+|\s+(?:at|@)\s+", re.IGNORECASE
)
_AT_SEPARATOR = re.compile(r"^\s+(?:at|@)\s+$", re.IGNORECASE)
_BULLET = re.compile(
    r"^[\u2022\u00b7\u25aa\u25cf\u25cb\u25ba\u2023\u2043*\u2013\u2014-]\s*"
)

# A dated heading line: long enough for "Qualification · Institution · a note", short
# enough that a sentence which happens to end in a year range is not one.
_DATED_HEADING_MAX_WORDS = 20
# A heading on a line of its own, above or below a line holding only the dates.
_BARE_HEADING_MAX_WORDS = 10
_BARE_HEADING_LOOKBACK = 2
_PLACE_CONNECTORS = frozenset({"of", "on", "upon", "the"})

# Punctuation left at the edges of a heading once its dates are cut out. A closing
# parenthesis stays on the heading side: "Engineer (Infrastructure)" ends in one.
_EDGE = " ,;:|\u00b7\u2022-\u2013\u2014"

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
    github_url: str | None = None


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
class ExtractedLanguage:
    """A language and how well it is spoken, as the CV put it."""

    name: str
    level: LanguageLevel


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
        enriched: Whether a language model complemented this read. Reported so the
            client can say which of the two passes produced what it is showing.
    """

    contact: ExtractedContact = field(default_factory=ExtractedContact)
    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    experiences: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    educations: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)
    languages: tuple[ExtractedLanguage, ...] = field(default_factory=tuple)
    enriched: bool = False


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
        if len(line.split()) == 1 and not _is_heading(line):
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

    return _dates_of(match)


def _dates_of(match: re.Match[str]) -> tuple[date | None, date | None]:
    """Turn a `_DATE_RANGE` match into dates.

    Args:
        match: A match of `_DATE_RANGE`.

    Returns:
        ``(start, end)``, ``end`` None for a current entry.
    """
    start = _as_date(match.group("m1") or match.group("n1"), match.group("y1"))
    if match.group("present"):
        return start, None
    return start, _as_date(
        match.group("m2") or match.group("n2"), match.group("y2"), end_of_range=True
    )


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
        month: A month name, abbreviation or number, if the entry gave one.
        year: A four-digit year.
        end_of_range: Whether this is the closing date, which defaults to December
            rather than January so a year-only range spans the whole year.

    Returns:
        The first of the month, or None if the year is unusable.
    """
    number: int | None = None
    if month:
        number = int(month) if month.isdigit() else _MONTHS.get(month.casefold())
    if number is None:
        number = 12 if end_of_range else 1
    try:
        return date(int(year), number, 1)
    except ValueError:  # pragma: no cover - the regex already bounds the year
        return None


def is_education(entry: ExtractedEntry) -> bool:
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


@dataclass(slots=True)
class _Heading:
    """An entry heading found in the text, before its parts are told apart.

    Attributes:
        first: Index of the heading's first line.
        last: Index of its last line — a heading can span two lines.
        parts: The heading text, one string per line it came from.
        start_date: The start, when a date range was found for it.
        end_date: The end, None for a current entry.
        dated: Whether a date range was found for it at all.
        inline: Whether the heading was split by a separator on one line, whose
            convention is employer first; separate lines usually put the title first.
    """

    first: int
    last: int
    parts: list[str]
    start_date: date | None = None
    end_date: date | None = None
    dated: bool = False
    inline: bool = True


@dataclass(frozen=True, slots=True)
class _Resolved:
    """A heading told apart into its fields."""

    organisation: str
    title: str
    location: str | None
    note: str | None


def _is_bullet(line: str) -> bool:
    """Report whether a line is a list item rather than a heading."""
    return bool(_BULLET.match(line))


def _words(text: str) -> list[str]:
    """Split a heading fragment into bare lowercase words, for the marker sets."""
    return [
        word.strip(".,;:()[]\"'")
        for word in text.casefold().replace("(", " ").replace("/", " ").split()
    ]


def _looks_like_a_bare_heading(line: str) -> bool:
    """Report whether a line could be a heading on a line of its own.

    Deliberately strict: the line before a date could as easily be the end of the
    previous role's text, and a wrong guess there turns a sentence into an employer.

    Args:
        line: A reflowed line.

    Returns:
        True for a short, capitalised, unpunctuated line that is not a list item.
    """
    words = line.split()
    first_letter = next((char for char in line if char.isalpha()), "")
    return (
        0 < len(words) <= _BARE_HEADING_MAX_WORDS
        and first_letter.isupper()
        and not _is_bullet(line)
        and ":" not in line
        and not line.rstrip().endswith((".", ",", ";"))
        and not _is_heading(line)
        and _DATE_RANGE.search(line) is None
    )


def _dated_line(line: str) -> tuple[str, re.Match[str]] | None:
    """Split a line that opens or closes with a date range into heading and dates.

    Args:
        line: A reflowed line.

    Returns:
        ``(heading text, date match)``, the text empty when the line holds only the
        dates, or None when no date range opens or closes the line.
    """
    matches = list(_DATE_RANGE.finditer(line))
    if not matches:
        return None
    last = matches[-1]
    if not line[last.end() :].strip(_EDGE + ")]"):
        return line[: last.start()].strip(_EDGE + "(["), last
    first = matches[0]
    if not line[: first.start()].strip(_EDGE + "(["):
        return line[first.end() :].strip(_EDGE + ")]"), first
    return None


def _find_headings(lines: list[str]) -> list[_Heading]:
    """Find every entry heading, and the dates that belong to each.

    Four layouts are recognised, because CVs use all of them:

    - dates at either end of the heading line (``Role, Employer   Jan 2021 - Present``);
    - dates alone on the line after an ``Employer, City — Role`` heading, which is also
      what a two-column layout reflows into;
    - dates alone on a line under one or two bare heading lines (``Role`` / ``Employer``
      / ``2019 - 2021``);
    - dates alone on a line *above* the heading.

    Args:
        lines: Reflowed lines.

    Returns:
        The headings, in document order.
    """
    headings: list[_Heading] = []
    consumed: set[int] = set()

    for index, line in enumerate(lines):
        if index in consumed or _is_bullet(line) or _is_heading(line):
            continue

        split = _dated_line(line)
        if split is not None and split[0]:
            text, match = split
            if len(text.split()) <= _DATED_HEADING_MAX_WORDS and not text.endswith("."):
                start, end = _dates_of(match)
                consumed.add(index)
                previous = headings[-1] if headings else None
                if (
                    previous is not None
                    and not previous.dated
                    and previous.last == index - 1
                ):
                    # The heading wrapped: "Employer — Principal Platform" then
                    # "Engineer (Infrastructure)  MAR 2021 - PRESENT".
                    previous.parts[-1] = f"{previous.parts[-1]} {text}"
                    previous.last = index
                    previous.start_date, previous.end_date = start, end
                    previous.dated = True
                else:
                    headings.append(
                        _Heading(index, index, [text], start, end, dated=True)
                    )
            continue

        if split is not None:
            _attach_bare_dates(lines, index, split[1], headings, consumed)
            continue

        if _ENTRY.match(line):
            headings.append(_Heading(index, index, [line]))
            consumed.add(index)
    return headings


def _attach_bare_dates(
    lines: list[str],
    index: int,
    match: re.Match[str],
    headings: list[_Heading],
    consumed: set[int],
) -> None:
    """Give a line holding only a date range to the heading it belongs to.

    Args:
        lines: Reflowed lines.
        index: The date line's index.
        match: Its date range.
        headings: The headings so far; appended to or updated in place.
        consumed: Indices already part of a heading; updated in place.
    """
    start, end = _dates_of(match)
    consumed.add(index)

    # An undated heading earlier on: these are its dates, however far down they sit.
    previous = headings[-1] if headings else None
    if previous is not None and not previous.dated:
        previous.start_date, previous.end_date, previous.dated = start, end, True
        return

    # One or two bare heading lines straight above the dates.
    above: list[int] = []
    cursor = index - 1
    while (
        cursor >= 0
        and len(above) < _BARE_HEADING_LOOKBACK
        and cursor not in consumed
        and _looks_like_a_bare_heading(lines[cursor])
    ):
        above.insert(0, cursor)
        cursor -= 1
    if above:
        consumed.update(above)
        headings.append(
            _Heading(
                above[0],
                index,
                [lines[i] for i in above],
                start,
                end,
                dated=True,
                inline=False,
            )
        )
        return

    # Otherwise the heading follows the dates.
    following = index + 1
    if following < len(lines) and _looks_like_a_bare_heading(lines[following]):
        consumed.add(following)
        headings.append(
            _Heading(
                index,
                following,
                [lines[following]],
                start,
                end,
                dated=True,
                inline=False,
            )
        )


def _split_outside_parentheses(text: str, separator: str) -> list[str]:
    """Split on a character, ignoring it inside parentheses.

    ``Computer Science courses (Python, Unix)`` is one fragment, not two.

    Args:
        text: The text to split.
        separator: A single character.

    Returns:
        The non-empty, stripped pieces.
    """
    pieces: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        depth += (char == "(") - (char == ")")
        if char == separator and depth <= 0:
            pieces.append("".join(current))
            current = []
            continue
        current.append(char)
    pieces.append("".join(current))
    return [piece.strip() for piece in pieces if piece.strip()]


def _fragments(heading: _Heading) -> tuple[list[str], bool, bool]:
    """Break a heading into its fragments.

    Args:
        heading: The heading.

    Returns:
        The fragments; whether the order is title first, which an ``X at Y`` heading
        or a heading on lines of its own implies; and whether any came from a comma,
        which unlike a dash also sits between an employer and its city.
    """
    fragments: list[str] = []
    title_first = not heading.inline
    by_comma = False
    for part in heading.parts:
        pieces = _STRONG_SEPARATORS.split(part)
        separators = _STRONG_SEPARATORS.findall(part)
        if any(_AT_SEPARATOR.match(found) for found in separators):
            title_first = True
        if len(pieces) == 1:
            pieces = _split_outside_parentheses(part, ",")
            by_comma = by_comma or len(pieces) > 1
        fragments.extend(piece.strip(_EDGE) for piece in pieces)
    return [fragment for fragment in fragments if fragment], title_first, by_comma


def _title_score(fragment: str) -> int:
    """Count the words that mark a fragment as a title or a qualification."""
    qualification = EDUCATION_MARKERS - ORGANISATION_MARKERS
    return sum(
        word in ROLE_MARKERS or word in qualification for word in _words(fragment)
    )


def _organisation_score(fragment: str) -> int:
    """Count the words that mark a fragment as an employer or an institution."""
    return sum(word in ORGANISATION_MARKERS for word in _words(fragment))


def _looks_like_a_location(fragment: str) -> bool:
    """Report whether a heading fragment reads as a place: ``Leeds``, ``York, UK``.

    Args:
        fragment: A heading fragment.

    Returns:
        True for a few capitalised words with no digits and no marker words.
    """
    words = fragment.split()
    if not 0 < len(words) <= _PLACE_MAX_WORDS or any(c.isdigit() for c in fragment):
        return False
    if _title_score(fragment) or _organisation_score(fragment):
        return False
    return (
        all(
            word[:1].isupper() or word.casefold() in _PLACE_CONNECTORS for word in words
        )
        and len(fragment) <= DEFAULT_LOCATION_MAX_LENGTH
    )


def _resolve(heading: _Heading) -> _Resolved:
    """Tell a heading's fragments apart into employer, title and location.

    Decided by what the words say — "Analyst", "University", "Ltd" — and only by
    position when they say nothing, because CVs write both ``Title, Employer`` and
    ``Employer, Title`` and the punctuation is the same.

    Args:
        heading: The heading.

    Returns:
        Its fields. The organisation or the title may be empty when the heading holds
        only one of them; `_entries` fills an employer in from a group heading.
    """
    fragments, title_first, by_comma = _fragments(heading)
    title_scores = [_title_score(f) - _organisation_score(f) for f in fragments]
    organisation_scores = [_organisation_score(f) for f in fragments]
    remaining = list(range(len(fragments)))

    title = organisation = ""
    if remaining and max(title_scores) > 0:
        index = title_scores.index(max(title_scores))
        title = fragments[index]
        remaining.remove(index)
    if remaining and max(organisation_scores[i] for i in remaining) > 0:
        index = max(remaining, key=lambda i: organisation_scores[i])
        organisation = fragments[index]
        remaining.remove(index)

    # Whatever the words did not decide, the position does. After a comma a place is
    # not taken for a title: "Globex Corporation, Leeds" is an employer and where it
    # is. After a dash it is: "Hooli, Cardiff — Warehouse Operations" says so.
    if not title and not organisation and title_first and len(remaining) >= 2:
        title, organisation = fragments[remaining[0]], fragments[remaining[1]]
        remaining = remaining[2:]
    if not organisation and remaining:
        organisation = fragments[remaining.pop(0)]
    if not title:
        positional = next(
            (
                i
                for i in remaining
                if not (by_comma and _looks_like_a_location(fragments[i]))
            ),
            None,
        )
        if positional is not None:
            title = fragments[positional]
            remaining.remove(positional)

    location: str | None = None
    notes: list[str] = []
    # "Employer, City" arrives as one fragment when a stronger separator split the line.
    head, _, tail = organisation.rpartition(",")
    tail = tail.strip()
    if head and _looks_like_a_location(tail):
        organisation, location = head.strip(), tail
    elif head and tail[:1].islower():
        # "Northfield College, alongside the BSc" is an aside, not a place.
        organisation = head.strip()
        notes.append(tail)

    for index in remaining:
        if location is None and _looks_like_a_location(fragments[index]):
            location = fragments[index]
        else:
            notes.append(fragments[index])
    return _Resolved(organisation, title, location, "; ".join(notes) or None)


def _entries(lines: list[str]) -> tuple[ExtractedEntry, ...]:
    """Read dated entries from the document's lines.

    Finds every heading first (`_find_headings`), then gives each the text up to the
    next heading or section heading as its description. That is what makes this
    tolerant of a scrambled reading order: dates and prose need only be *near* their
    heading, not on the same line.

    A heading that names only an employer, straight above headings that name only a
    title, is a group — several roles at one employer — and gives them its employer
    rather than being proposed as a role of its own.

    Args:
        lines: The document's reflowed lines.

    Returns:
        The entries found, in document order.
    """
    headings = _find_headings(lines)
    resolved = [_resolve(heading) for heading in headings]
    starts = {heading.first for heading in headings}

    found: list[ExtractedEntry] = []
    group: _Resolved | None = None
    for position, (heading, fields) in enumerate(zip(headings, resolved, strict=True)):
        following = resolved[position + 1] if position + 1 < len(resolved) else None
        if (
            fields.organisation
            and not fields.title
            and following is not None
            and not following.organisation
            and following.title
        ):
            group = fields
            continue

        organisation, location = fields.organisation, fields.location
        if organisation:
            group = None
        elif group is not None:
            organisation, location = group.organisation, location or group.location

        body: list[str] = [fields.note] if fields.note else []
        for index in range(heading.last + 1, len(lines)):
            if index in starts or _is_heading(lines[index]):
                break
            body.append(lines[index])
        text = " ".join(body)
        start, end = heading.start_date, heading.end_date
        if not heading.dated:
            start, end = _parse_dates(text)

        description = _DATE_RANGE.sub("", text).strip(" -\u2013\u2014")
        found.append(
            ExtractedEntry(
                organisation=organisation.strip(),
                title=fields.title.strip(),
                location=(location or "").strip() or None,
                start_date=start,
                end_date=end,
                description=description or None,
            )
        )
    return tuple(found)


# How CVs word a level, mapped onto the five the profile keeps.
_LEVEL_WORDS: dict[str, LanguageLevel] = {
    "native": LanguageLevel.NATIVE,
    "mother tongue": LanguageLevel.NATIVE,
    "bilingual": LanguageLevel.NATIVE,
    "fluent": LanguageLevel.FLUENT,
    "proficient": LanguageLevel.FLUENT,
    "c2": LanguageLevel.FLUENT,
    "advanced": LanguageLevel.ADVANCED,
    "c1": LanguageLevel.ADVANCED,
    "upper intermediate": LanguageLevel.INTERMEDIATE,
    "intermediate": LanguageLevel.INTERMEDIATE,
    "b2": LanguageLevel.INTERMEDIATE,
    "b1": LanguageLevel.INTERMEDIATE,
    "basic": LanguageLevel.BASIC,
    "beginner": LanguageLevel.BASIC,
    "elementary": LanguageLevel.BASIC,
    "a2": LanguageLevel.BASIC,
    "a1": LanguageLevel.BASIC,
}
_LANGUAGE_ENTRY = re.compile(
    r"^(?P<name>[A-Z][\w-]+(?: [A-Z][\w-]+)?)\s*\((?P<level>[^)]*)\)"
)
_LANGUAGES_LABEL = re.compile(r"^languages?\s*[:\-\u2013\u2014]\s*", re.IGNORECASE)


def _level(text: str) -> LanguageLevel | None:
    """Read a level out of what a CV put in brackets: "fluent, daily working language".

    Args:
        text: The bracketed text.

    Returns:
        The level, or None when the words say none.
    """
    lowered = text.casefold()
    for words, level in _LEVEL_WORDS.items():
        if re.search(rf"\b{re.escape(words)}\b", lowered):
            return level
    return None


def _languages(lines: list[str]) -> tuple[ExtractedLanguage, ...]:
    """Read languages from a "Languages: X (native), Y (fluent)" line or section.

    Only entries that state a level are proposed: a bare word in a languages list is
    as likely to be a programming language as a spoken one.

    Args:
        lines: The reflowed lines.

    Returns:
        The languages, in the order the CV lists them.
    """
    candidates: list[str] = []
    for index, line in enumerate(lines):
        labelled = _LANGUAGES_LABEL.match(line)
        if labelled:
            candidates.append(line[labelled.end() :])
        elif _section_for(line) == "other" and line.casefold().startswith("language"):
            candidates.extend(lines[index + 1 : index + 2])

    found: list[ExtractedLanguage] = []
    for text in candidates:
        for fragment in _split_outside_parentheses(text, ","):
            match = _LANGUAGE_ENTRY.match(fragment.strip())
            level = _level(match.group("level")) if match else None
            if match and level and match.group("name") not in {f.name for f in found}:
                found.append(ExtractedLanguage(name=match.group("name"), level=level))
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

    github = _GITHUB.search(without_emails)

    website: str | None = None
    for candidate in _WEBSITE.finditer(without_emails):
        value = candidate.group(0)
        # LinkedIn and GitHub match the generic pattern too; each has its own field.
        if "linkedin.com" not in value.lower() and "github.com" not in value.lower():
            website = value
            break

    return ExtractedContact(
        email=email.group(0) if email else None,
        phone=_phone(raw),
        linkedin_url=linkedin.group(0) if linkedin else None,
        website_url=website,
        github_url=github.group(0) if github else None,
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
    # PDF text keeps typographic ligatures: "ﬂuent" is not "fluent" to a regex.
    cv_text = unicodedata.normalize("NFKC", cv_text)
    lines = _reflow(cv_text)
    sections = _split_sections(lines)
    flat = _WHITESPACE.sub(" ", cv_text)

    # Gathered whole-document then classified: on a multi-column CV the headings
    # cannot be trusted to bound sections. See `is_education`.
    entries = _entries(lines)
    headline, location = _header_facts(cv_text)

    return ExtractedProfile(
        contact=_contact(flat, cv_text),
        headline=headline,
        summary=_summary(sections.get("summary", [])),
        location=location,
        experiences=tuple(e for e in entries if not is_education(e)),
        educations=tuple(e for e in entries if is_education(e)),
        skills=_skills(sections.get("skills", [])),
        languages=_languages(lines),
    )
