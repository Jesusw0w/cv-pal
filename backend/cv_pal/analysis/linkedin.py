"""Deterministic parsing and review of a LinkedIn profile.

No language model, no network, and above all **no fetch of linkedin.com**. Automated
access is against LinkedIn's terms and the account it endangers is the user's own, so
the profile arrives as a document the user exported themselves — see
`docs/linkedin-import.md` for the routes and PLANNING.md Phase 10 for the reasoning.

Three text shapes reach this module and only one of them is tidy:

* **LinkedIn's own "Save to PDF"** puts a sidebar first (``Contact``, ``Top Skills``,
  ``Languages``) and the profile body after it. Availability is inconsistent, so it is
  supported and never depended on.
* **Browser print-to-PDF** is the route that works for everyone. It carries navigation
  chrome around the content, and anything the user left collapsed is simply absent —
  which is why a suspiciously empty section is reported as *possibly collapsed* rather
  than as *missing*.
* **Paste** loses the section boundaries entirely. Rather than report every section as
  missing, `LinkedInSource.has_sections` is false and the review says which mode
  produced it.

Everything here is a pure function over text: same input, same review.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import date

from cv_pal.analysis.extraction import ExtractedEntry, find_date_range
from cv_pal.analysis.keywords import CoverageReport, analyse, canonical
from cv_pal.constants import (
    DEFAULT_LINKEDIN_MIN_ABOUT_WORDS,
    DEFAULT_LINKEDIN_MIN_HEADLINE_WORDS,
    DEFAULT_LINKEDIN_MIN_SKILLS,
    LinkedInIssueKind,
    LinkedInSectionStatus,
    LinkedInSource,
)

_PROFILE_URL = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/in/(?P<slug>[\w%-]+)", re.IGNORECASE
)

# Headings LinkedIn emits, in render order. The trailing markers are what tell a
# LinkedIn export from any other CV.
_SECTION_HEADINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("contact", ("contact",)),
    ("top_skills", ("top skills",)),
    ("languages", ("languages",)),
    ("certifications", ("certifications", "licenses & certifications")),
    ("honors", ("honors-awards", "honors & awards")),
    ("about", ("summary", "about")),
    ("experience", ("experience",)),
    ("education", ("education",)),
    ("skills", ("skills", "skills & endorsements")),
    ("recommendations", ("recommendations", "recommendations received")),
    ("volunteering", ("volunteer experience", "volunteering")),
    ("projects", ("projects",)),
)

# Present in a LinkedIn export and essentially nowhere else.
_LINKEDIN_FINGERPRINTS: tuple[str, ...] = (
    "top skills",
    "people also viewed",
    "recommendations received",
    "skills & endorsements",
    "www.linkedin.com/in/",
    "linkedin.com/in/",
    "page 1 of",
)

# LinkedIn stacks a position over three lines rather than using a CV's em dash.
# Per-role durations are parenthesised, total tenure is bare — hence optional.
_DURATION = re.compile(
    r"\(?\s*(?:less than a year|\d+\s+(?:year|month)s?(?:\s+\d+\s+months?)?)\s*\)?",
    re.IGNORECASE,
)
_ENDORSEMENTS = re.compile(r"\b\d+\s+endorsements?\b", re.IGNORECASE)
# Used to lift the qualification out of "Master's degree, Finance · (2016 - 2018)".
_DATE_IN_LINE = re.compile(
    r"\(?\s*(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2}\s*"
    r"(?:[-\u2013\u2014]|\bto\b)\s*"
    r"(?:present|current|now|ongoing|(?:[A-Za-z]{3,9}\s+)?(?:19|20)\d{2})\s*\)?",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"[ \t\xa0]+")


@dataclass(frozen=True, slots=True)
class LinkedInSnapshot:
    """A parsed profile, as imported. A record of the document, not of the truth.

    Attributes:
        source: Which ingestion route produced it.
        profile_url: The profile URL found in the document, when it carried one.
        name: The profile owner's name, when the layout exposed it.
        headline: The line under the name — what recruiter search weights hardest.
        about: The About/Summary prose.
        positions: Roles, newest first where dates allowed ordering.
        educations: Qualifications.
        skills: Skill names, deduplicated on their canonical form.
        sections_found: Section keys the document actually contained.
        text: The full extracted text, kept so a later review can be recomputed
            without asking the user to upload again.
    """

    source: LinkedInSource
    profile_url: str | None = None
    name: str | None = None
    headline: str | None = None
    about: str | None = None
    positions: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    educations: tuple[ExtractedEntry, ...] = field(default_factory=tuple)
    skills: tuple[str, ...] = field(default_factory=tuple)
    sections_found: tuple[str, ...] = field(default_factory=tuple)
    text: str = ""

    @property
    def is_empty(self) -> bool:
        """Whether nothing usable came out of the document.

        Returns:
            True when the parse found no headline, prose, role, qualification or skill.
        """
        return not any(
            (self.headline, self.about, self.positions, self.educations, self.skills)
        )


@dataclass(frozen=True, slots=True)
class SectionReview:
    """One section's verdict.

    Attributes:
        section: Stable key, safe to branch on in a UI.
        status: Missing, thin, or good enough.
        detail: What to do about it, phrased as the cost of leaving it.
    """

    section: str
    status: LinkedInSectionStatus
    detail: str


@dataclass(frozen=True, slots=True)
class ConsistencyIssue:
    """Somewhere the LinkedIn profile and the career profile disagree.

    Attributes:
        kind: Stable identifier for the kind of disagreement.
        organisation: The employer the disagreement is about.
        detail: Both sides of it, so the user can tell which one is wrong.
    """

    kind: LinkedInIssueKind
    organisation: str
    detail: str


@dataclass(frozen=True, slots=True)
class LinkedInReview:
    """The whole review of an imported profile.

    Attributes:
        score: 0 to 100 over the sections that could be judged.
        sections: Per-section verdicts, worst first.
        coverage: Headline and About measured against the user's target roles, or None
            when no target roles have been set.
        consistency: Disagreements with the career profile.
        source: Which ingestion route the snapshot came from.
        note: What this review could not do, given that route.
    """

    score: int
    sections: tuple[SectionReview, ...]
    coverage: CoverageReport | None
    consistency: tuple[ConsistencyIssue, ...]
    source: LinkedInSource
    note: str


def looks_like_linkedin(text: str) -> bool:
    """Report whether a document reads as a LinkedIn profile export.

    Detecting this server-side is most of the convenience a scraper would have bought:
    the user uploads whatever LinkedIn gave them without first having to tell CV Pal
    what it is.

    Args:
        text: Extracted document text.

    Returns:
        True when the document carries LinkedIn's structural fingerprints.
    """
    lowered = text.lower()
    hits = sum(1 for marker in _LINKEDIN_FINGERPRINTS if marker in lowered)
    # The URL alone is conclusive; otherwise two markers, so a CV that merely lists
    # a LinkedIn address is not mistaken for an export.
    return bool(_PROFILE_URL.search(text)) or hits >= 2


def _normalise(text: str) -> list[str]:
    """Collapse whitespace and drop the lines LinkedIn adds around the content.

    Args:
        text: Raw extracted text.

    Returns:
        Non-empty lines with page furniture removed.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        line = _WHITESPACE.sub(" ", raw).strip()
        if not line:
            continue
        lowered = line.lower()
        # Print-to-PDF page furniture, and the endorsement counts that would otherwise
        # be read as skill names.
        if lowered.startswith("page ") and " of " in lowered:
            continue
        if _ENDORSEMENTS.fullmatch(line):
            continue
        lines.append(line)
    return lines


def _heading_key(line: str) -> str | None:
    """Return the section key a line is a heading for, if it is one.

    Args:
        line: A single normalised line.

    Returns:
        The section key, or None when the line is body content.
    """
    lowered = line.lower().strip(" :")
    # A heading is a short line, so a sentence mentioning "experience" is not one.
    if len(lowered.split()) > 3:
        return None
    for key, aliases in _SECTION_HEADINGS:
        if lowered in aliases:
            return key
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Group lines under the section heading that precedes them.

    Args:
        lines: Normalised document lines.

    Returns:
        Section key to its lines. Content before the first heading is kept under
        ``_preamble``, which is where the name and headline live.
    """
    sections: dict[str, list[str]] = {"_preamble": []}
    current = "_preamble"
    for line in lines:
        key = _heading_key(line)
        if key is not None:
            current = key
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def _parse_positions(lines: list[str]) -> tuple[ExtractedEntry, ...]:
    """Read roles out of the Experience section.

    Validated against a real "Save to PDF" export, whose shape is the reason this is a
    stateful scan rather than a window around each date line::

        Northgate Capital Markets              <- employer
        5 years 6 months             <- total tenure, present only when several roles
        Senior Software Developer    <- role 1
        June 2025 - Present (1 year 2 months)
        Data Analyst                 <- role 2, same employer
        April 2023 - August 2025 (2 years 5 months)
        Lisbon, Portugal             <- location, attaches to the role above

    **Several roles at one employer name the employer once.** Reading a fixed two lines
    back therefore picks up the tenure line, or the previous role's location, as the
    employer — which is exactly what it did before this was rewritten. So the employer
    is carried forward instead: a line that is nothing but a duration promotes the line
    before it to employer, and a second consecutive unconsumed line does the same.

    Args:
        lines: Lines belonging to the Experience section.

    Returns:
        The roles found, in document order.
    """
    entries: list[ExtractedEntry] = []
    employer: str | None = None
    pending: str | None = None
    after_date = False

    for line in lines:
        stripped = _DURATION.sub("", line).strip(" ·")
        span = find_date_range(stripped) if stripped else None

        if span is None and _DURATION.fullmatch(line.strip()):
            # A bare tenure line ("5 years 6 months") only ever follows an employer.
            if pending is not None:
                employer, pending = pending, None
            after_date = False
            continue

        if span is not None:
            start, end = span
            if pending is not None:
                entries.append(
                    ExtractedEntry(
                        organisation=employer or pending,
                        title=pending,
                        start_date=start,
                        end_date=end,
                    )
                )
                pending = None
            after_date = True
            continue

        if after_date:
            after_date = False
            # The next role's title sits in the same place when there is no location.
            # The comma is the tell: titles rarely have one, locations always do.
            if "," in line and entries and entries[-1].location is None:
                entries[-1] = replace(entries[-1], location=line)
                continue

        if pending is not None:
            # Two headings in a row: the first was the employer, the second is the role.
            employer = pending
        pending = line

    return tuple(entries)


def _parse_educations(lines: list[str]) -> tuple[ExtractedEntry, ...]:
    """Read qualifications out of the Education section.

    Education is laid out differently from experience — the qualification and its dates
    share a line, with the institution above::

        Atlântico Business School
        Master's degree, Finance · (2016 - 2018)

    So the title comes from whatever survives on the date line once the dates are
    removed, and only falls back to the line above when the entry gave none.

    Args:
        lines: Lines belonging to the Education section.

    Returns:
        The qualifications found, in document order.
    """
    entries: list[ExtractedEntry] = []
    for index, line in enumerate(lines):
        span = find_date_range(line)
        if span is None:
            continue
        start, end = span

        remainder = _DATE_IN_LINE.sub("", line).strip(" \xa0\u00b7()-\u2013\u2014,")
        previous = lines[index - 1] if index > 0 else None
        if remainder:
            organisation = previous or remainder
            title = remainder
        elif previous is not None:
            organisation = lines[index - 2] if index > 1 else previous
            title = previous
        else:
            continue

        entries.append(
            ExtractedEntry(
                organisation=organisation,
                title=title,
                start_date=start,
                end_date=end,
            )
        )
    return tuple(entries)


def _identity(
    lines: list[str], sections: dict[str, list[str]]
) -> tuple[str | None, str | None]:
    """Find the name and headline, wherever the layout put them.

    The two PDF routes disagree about this. Print-to-PDF leads with the identity block,
    so it lands in the preamble. **"Save to PDF" renders the whole sidebar first** —
    Contact, Top Skills, Languages — and only then the name, headline and location,
    which therefore land at the tail of whichever sidebar section came last. Reading the
    preamble alone found neither on a real export.

    Args:
        lines: All normalised lines.
        sections: The document split by heading.

    Returns:
        ``(name, headline)``, either of which may be None.
    """
    preamble = sections.get("_preamble", [])
    if len(preamble) >= 2:
        return preamble[0], preamble[1]

    # The identity block is the run immediately before the first body section.
    body_keys = ("about", "experience", "education")
    first_body = next(
        (index for index, line in enumerate(lines) if _heading_key(line) in body_keys),
        None,
    )
    if first_body is None or first_body < 2:
        return (preamble[0] if preamble else None), None

    block = lines[max(0, first_body - 3) : first_body]
    # Name, headline, location — in that order. A two-line block is name and headline.
    if len(block) >= 3:
        return block[0], block[1]
    if len(block) == 2:
        return block[0], block[1]
    return block[0], None


def _parse_skills(lines: list[str]) -> tuple[str, ...]:
    """Read skill names, deduplicated on their canonical form.

    Args:
        lines: Lines from the Skills and Top Skills sections.

    Returns:
        Skill names in first-seen order.
    """
    seen: set[str] = set()
    skills: list[str] = []
    for line in lines:
        name = line.strip(" ·•-")
        # LinkedIn lists one skill per line; anything sentence-length is prose that
        # landed in the section, not a skill.
        if not name or len(name.split()) > 5:
            continue
        key = canonical(name)
        if key in seen:
            continue
        seen.add(key)
        skills.append(name)
    return tuple(skills)


def parse_profile(text: str, *, source: LinkedInSource) -> LinkedInSnapshot:
    """Parse an exported LinkedIn profile into a snapshot.

    Args:
        text: Extracted document text.
        source: Which ingestion route produced it.

    Returns:
        The parsed snapshot, which may be largely empty when the document did not
        survive text extraction.
    """
    lines = _normalise(text)
    sections = _split_sections(lines)

    match = _PROFILE_URL.search(text)
    profile_url = (
        f"https://www.linkedin.com/in/{match.group('slug')}" if match else None
    )

    name, headline = _identity(lines, sections)

    about_lines = sections.get("about", [])
    about = " ".join(about_lines).strip() or None

    skills = _parse_skills(sections.get("skills", []) + sections.get("top_skills", []))

    found = tuple(key for key in sections if key != "_preamble" and sections[key])

    return LinkedInSnapshot(
        source=source,
        profile_url=profile_url,
        name=name,
        headline=headline,
        about=about,
        positions=_parse_positions(sections.get("experience", [])),
        educations=_parse_educations(sections.get("education", [])),
        skills=skills,
        sections_found=found,
        text=text,
    )


def _headline_review(snapshot: LinkedInSnapshot) -> SectionReview:
    """Judge the headline.

    Args:
        snapshot: The parsed profile.

    Returns:
        The headline's verdict.
    """
    words = len((snapshot.headline or "").split())
    if not snapshot.headline:
        return SectionReview(
            section="headline",
            status=LinkedInSectionStatus.MISSING,
            detail=(
                "No headline found. It is the line recruiters read first and the field "
                "their search weights hardest."
            ),
        )
    if words < DEFAULT_LINKEDIN_MIN_HEADLINE_WORDS:
        return SectionReview(
            section="headline",
            status=LinkedInSectionStatus.THIN,
            detail=(
                f"Only {words} word(s). A headline that is just a job title wastes the "
                "most searchable field on the profile."
            ),
        )
    return SectionReview(
        section="headline",
        status=LinkedInSectionStatus.OK,
        detail=snapshot.headline,
    )


def _about_review(snapshot: LinkedInSnapshot) -> SectionReview:
    """Judge the About section.

    Args:
        snapshot: The parsed profile.

    Returns:
        The About section's verdict.
    """
    words = len((snapshot.about or "").split())
    if not snapshot.about:
        return SectionReview(
            section="about",
            status=LinkedInSectionStatus.MISSING,
            detail=(
                "No About section found. If you have one, it may have been collapsed "
                "when the PDF was made — expand every 'see more' and import again."
            ),
        )
    if words < DEFAULT_LINKEDIN_MIN_ABOUT_WORDS:
        return SectionReview(
            section="about",
            status=LinkedInSectionStatus.THIN,
            detail=(
                f"About is {words} words. This is the only place you control the "
                "narrative, and recruiter search reads it."
            ),
        )
    return SectionReview(
        section="about",
        status=LinkedInSectionStatus.OK,
        detail=f"{words} words.",
    )


def _count_review(
    section: str, count: int, minimum: int, *, missing: str, thin: str, ok: str
) -> SectionReview:
    """Judge a section by how many entries it holds.

    Args:
        section: The section key.
        count: Entries found.
        minimum: Below this the section reads as under-filled.
        missing: Detail to use when nothing was found.
        thin: Detail template taking the count.
        ok: Detail template taking the count.

    Returns:
        The section's verdict.
    """
    if count == 0:
        return SectionReview(
            section=section, status=LinkedInSectionStatus.MISSING, detail=missing
        )
    if count < minimum:
        return SectionReview(
            section=section,
            status=LinkedInSectionStatus.THIN,
            detail=thin.format(count=count),
        )
    return SectionReview(
        section=section, status=LinkedInSectionStatus.OK, detail=ok.format(count=count)
    )


def _same_organisation(left: str, right: str) -> bool:
    """Compare two employer names loosely enough to survive suffixes.

    Args:
        left: One name.
        right: The other.

    Returns:
        True when they read as the same employer.
    """
    a, b = canonical(left), canonical(right)
    return a == b or a.startswith(b) or b.startswith(a)


def _consistency(
    snapshot: LinkedInSnapshot, experiences: list[ExtractedEntry]
) -> tuple[ConsistencyIssue, ...]:
    """Compare the imported profile against the career profile.

    Both records describe one career, so a disagreement is visible to any recruiter who
    opens both. Reported, never auto-corrected: which side is right is the user's call.

    Args:
        snapshot: The parsed LinkedIn profile.
        experiences: The roles on the career profile.

    Returns:
        Every disagreement found, employer-level first.
    """
    issues: list[ConsistencyIssue] = []

    for position in snapshot.positions:
        match = next(
            (
                experience
                for experience in experiences
                if _same_organisation(experience.organisation, position.organisation)
            ),
            None,
        )
        if match is None:
            issues.append(
                ConsistencyIssue(
                    kind=LinkedInIssueKind.EMPLOYER_ONLY_ON_LINKEDIN,
                    organisation=position.organisation,
                    detail=(
                        f"{position.organisation} is on LinkedIn but not on "
                        "your career "
                        "profile, so nothing CV Pal generates can mention it."
                    ),
                )
            )
            continue

        if canonical(match.title) != canonical(position.title):
            issues.append(
                ConsistencyIssue(
                    kind=LinkedInIssueKind.TITLE_DIFFERS,
                    organisation=position.organisation,
                    detail=(
                        f"Title differs at {position.organisation}: "
                        f"'{position.title}' on LinkedIn, '{match.title}' on your "
                        "profile."
                    ),
                )
            )

        if _dates_differ(match, position):
            issues.append(
                ConsistencyIssue(
                    kind=LinkedInIssueKind.DATES_DIFFER,
                    organisation=position.organisation,
                    detail=(
                        f"Dates differ at {position.organisation}: "
                        f"{_format_span(position)} on LinkedIn, "
                        f"{_format_span(match)} on your profile."
                    ),
                )
            )

    linked_organisations = [position.organisation for position in snapshot.positions]
    for experience in experiences:
        if not any(
            _same_organisation(experience.organisation, name)
            for name in linked_organisations
        ):
            issues.append(
                ConsistencyIssue(
                    kind=LinkedInIssueKind.EMPLOYER_ONLY_ON_PROFILE,
                    organisation=experience.organisation,
                    detail=(
                        f"{experience.organisation} is on your career profile but not "
                        "on LinkedIn. A recruiter comparing the two sees a gap."
                    ),
                )
            )

    return tuple(issues)


def _dates_differ(left: ExtractedEntry, right: ExtractedEntry) -> bool:
    """Compare two entries' spans, ignoring the day of the month.

    LinkedIn records month precision and a CV often records only a year, so only a
    disagreement both sides actually stated is reported.

    Args:
        left: One entry.
        right: The other.

    Returns:
        True when the stated dates disagree.
    """
    return _year_of(left.start_date) != _year_of(right.start_date) or _year_of(
        left.end_date
    ) != _year_of(right.end_date)


def _year_of(value: date | None) -> int | None:
    """Return an entry date's year.

    Args:
        value: The date, or None when the entry is current.

    Returns:
        The year, or None.
    """
    return None if value is None else value.year


def _format_span(entry: ExtractedEntry) -> str:
    """Render an entry's dates for a message a user has to act on.

    Args:
        entry: The entry.

    Returns:
        A readable span.
    """
    start = entry.start_date.year if entry.start_date else "?"
    end = entry.end_date.year if entry.end_date else "present"
    return f"{start}\u2013{end}"


def review(
    snapshot: LinkedInSnapshot,
    *,
    experiences: list[ExtractedEntry],
    target_roles: list[str],
) -> LinkedInReview:
    """Review an imported profile against itself, the career profile and the goals.

    Args:
        snapshot: The parsed profile.
        experiences: Roles on the career profile, for the consistency check.
        target_roles: The roles the user is aiming at, for keyword coverage.

    Returns:
        The full review.
    """
    sections: list[SectionReview] = [
        _headline_review(snapshot),
        _about_review(snapshot),
        _count_review(
            "experience",
            len(snapshot.positions),
            1,
            missing=(
                "No roles found. If your Experience section is filled in, it was "
                "probably collapsed when the PDF was made."
            ),
            thin="{count} role found.",
            ok="{count} roles.",
        ),
        _count_review(
            "education",
            len(snapshot.educations),
            1,
            missing="No education found.",
            thin="{count} entry.",
            ok="{count} entries.",
        ),
        _count_review(
            "skills",
            len(snapshot.skills),
            DEFAULT_LINKEDIN_MIN_SKILLS,
            missing=(
                "No skills found. Recruiter search filters on these before a human "
                "reads anything."
            ),
            thin=(
                "Only {count} skill(s). Recruiter search filters on these, and a short "
                "list drops you out of results you would otherwise be in."
            ),
            ok="{count} skills.",
        ),
    ]

    # Paste has no section boundaries, so "missing" would be an artefact of the
    # import route rather than a fact. Say what could not be judged instead.
    if not snapshot.source.has_sections:
        sections = [
            section
            for section in sections
            if section.status is not LinkedInSectionStatus.MISSING
        ]
        note = (
            "Pasted text has no section boundaries, so only what could be "
            "recognised is "
            "scored. Import a print-to-PDF for the full section-by-section review."
        )
    else:
        note = (
            "Anything you left collapsed when exporting is absent from the document, "
            "and reads here as missing."
        )

    coverage = (
        analyse(_searchable_text(snapshot), " ".join(target_roles))
        if target_roles
        else None
    )

    ranking = {
        LinkedInSectionStatus.MISSING: 0,
        LinkedInSectionStatus.THIN: 1,
        LinkedInSectionStatus.OK: 2,
    }
    ordered = tuple(sorted(sections, key=lambda item: ranking[item.status]))

    return LinkedInReview(
        score=_score(ordered),
        sections=ordered,
        coverage=coverage,
        consistency=_consistency(snapshot, experiences),
        source=snapshot.source,
        note=note,
    )


def _searchable_text(snapshot: LinkedInSnapshot) -> str:
    """Join the fields recruiter search actually indexes.

    Args:
        snapshot: The parsed profile.

    Returns:
        Headline, About and skills as one document.
    """
    return " ".join(
        part
        for part in (snapshot.headline, snapshot.about, " ".join(snapshot.skills))
        if part
    )


def _score(sections: tuple[SectionReview, ...]) -> int:
    """Score the profile over the sections that could be judged.

    Args:
        sections: The per-section verdicts.

    Returns:
        0 to 100, or 0 when nothing could be judged at all.
    """
    if not sections:
        return 0
    points = {
        LinkedInSectionStatus.MISSING: 0,
        LinkedInSectionStatus.THIN: 1,
        LinkedInSectionStatus.OK: 2,
    }
    earned = sum(points[section.status] for section in sections)
    return round(earned / (len(sections) * 2) * 100)


__all__ = [
    "ConsistencyIssue",
    "LinkedInReview",
    "LinkedInSnapshot",
    "SectionReview",
    "looks_like_linkedin",
    "parse_profile",
    "review",
]
