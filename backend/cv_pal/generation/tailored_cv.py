"""Rendering a CV for one posting, from the career profile and nothing else.

This is Phase 8's first slice, and it implements exactly **one** of the three permitted
transforms from PLANNING → *The three permitted transforms*:

1. **Surface** — a fact already on the profile that a generic CV buries or omits is
   brought forward because this posting asks for it. A *selection and ordering* change.
2. **Substitute within an equivalence class** — the posting's spelling replaces the
   user's for the same thing, and **only where `SKILL_ALIASES` asserts they are the
   same**. See `substitute` for why that gate, and not canonical equality, is what makes
   it safe — and for how it satisfies PLANNING's requirement to disable the transform
   outside software without needing to detect anyone's occupation.
3. Rephrase — **not built here.** It needs a model, and everything below works on a
   fresh install with none configured.

Neither built transform can fabricate. Surfacing moves facts around; substituting swaps
one asserted-equivalent word for another. Nothing writes a new claim.

## The grounding invariant

> Every content string in the rendered document is copied verbatim from a profile row
> or from the user's own account details.

Nothing here composes prose about the user. The only text this module authors is
structural — headings, the date separator, the `Relevant here:` label — and that is
fixed. The one exception is deliberate and narrow: transform 2 renders a word taken
from the posting, which is why every such word is recorded in `substitutions` and the
grounding test is handed that list explicitly rather than inferring it.

`test_generation.py` pins the invariant by asserting every rendered value is either a
profile value or a recorded substitution, so a future "small improvement" that starts
writing summaries fails the suite rather than shipping.

That is also what makes the *Application quality gate*'s grounding check (PLANNING →
*The checks*) satisfiable by construction rather than by inspection afterwards.

## What is deliberately absent

- **No reordering of roles.** The spec says "select and order the most relevant
  experience", and reverse-chronological is kept anyway: it is what parsers expect, and
  shuffling roles by relevance breaks the date sequence an ATS uses to compute tenure.
  Relevance is expressed *inside* each role instead, by surfacing the skills that role
  evidences and this posting wants.
- **No page budget.** It needs a renderer that knows about pages; Markdown does not.
- **No unevidenced skills.** A skill no role demonstrates is a claim, not a fact — the
  same rule `job_service.profile_as_text` already applies to scoring. They are reported
  as omitted rather than silently dropped, so the user can go and evidence them.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from cv_pal.analysis.keywords import Keyword, canonical, extract_keywords
from cv_pal.analysis.vocabulary import SKILL_ALIASES
from cv_pal.constants import (
    DEFAULT_MAX_REPORTED_GAPS,
    DEFAULT_MAX_SURFACED_SKILLS_PER_ROLE,
)

# Case-preserving, because transform 2 quotes the posting's own spelling back. Mirrors
# `keywords._TOKEN`, which lowercases as it goes and so cannot be reused here.
_SPELLING = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#./\-]*")

# ASCII only. An en dash or middot is what a CV normally uses, and both are what
# arrives mangled after a DOCX or PDF round trip into an ATS.
_RANGE = "-"
_SEPARATOR = " | "
# Fixed structural text, never derived from the posting. Named so the grounding test
# can allow exactly this and nothing else that resembles it.
_RELEVANT_LABEL = "Relevant here: "

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass(frozen=True, slots=True)
class SkillFact:
    """One skill on the profile, with the roles that demonstrate it.

    Attributes:
        name: The user's own spelling, which is what gets rendered.
        canonical_name: The alias-resolved form, which is what gets compared.
        evidenced_by: Ids of the experiences demonstrating it. Empty means the skill is
            a claim rather than a fact, and it is left out of the document.
    """

    name: str
    canonical_name: str
    evidenced_by: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ExperienceFact:
    """One role on the profile."""

    id: int
    title: str
    organisation: str
    start_date: date
    end_date: date | None
    location: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class EducationFact:
    """One qualification on the profile."""

    institution: str
    qualification: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileFacts:
    """Everything the generator is allowed to draw on.

    A plain snapshot rather than the ORM rows, so the generator is pure, synchronous and
    testable without a database — and so it is obvious by inspection that there is no
    other source it could reach for.
    """

    full_name: str | None
    email: str
    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    phone: str | None = None
    website_url: str | None = None
    linkedin_url: str | None = None
    experiences: tuple[ExperienceFact, ...] = field(default_factory=tuple)
    educations: tuple[EducationFact, ...] = field(default_factory=tuple)
    skills: tuple[SkillFact, ...] = field(default_factory=tuple)


class BlockKind(StrEnum):
    """What a block is, so each renderer can decide how to present it.

    Semantic rather than visual — `ROLE` says "this names a job", not "make this bold".
    Markdown and DOCX disagree about how to express that, and an ATS reads the DOCX
    style name rather than anything visual, so the meaning has to survive to both.
    """

    NAME = "name"
    HEADLINE = "headline"
    CONTACT = "contact"
    SECTION = "section"
    ENTRY = "entry"
    META = "meta"
    BODY = "body"


@dataclass(frozen=True, slots=True)
class Block:
    """One laid-out piece of the document.

    Attributes:
        kind: What it is.
        text: The text, already assembled. Every block's text is either a profile value,
            a join of profile values, or one of this module's fixed structural strings —
            which is the property `content_values` and the grounding test check.
    """

    kind: BlockKind
    text: str


@dataclass(frozen=True, slots=True)
class Substitution:
    """The posting's wording used in place of the user's, for the same thing.

    Transform 2 from PLANNING, and the reason it is safe here and nowhere else: the
    alias map *asserts* the two spellings name one thing. It is recorded per use so the
    user can see every word that is not literally theirs.

    Attributes:
        from_term: The user's own spelling, as stored on the profile.
        to_term: The posting's spelling, used in the document.
        via: The canonical form the alias map resolved both to.
    """

    from_term: str
    to_term: str
    via: str


@dataclass(frozen=True, slots=True)
class Surfaced:
    """A profile fact brought forward because this posting asked for it.

    This is the rationale the spec wants per change: the posting's term, whether it was
    a hard requirement, the user's own wording for it, and the roles that back it.

    Attributes:
        term: The posting's canonical term.
        required: Whether the posting stated it as a requirement.
        skill: The user's spelling of the matching skill.
        evidence: Roles demonstrating it, as "Title, Organisation".
    """

    term: str
    required: bool
    skill: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Gap:
    """A term the posting asks for that the profile cannot evidence.

    Named and ranked, **never written into the document**. This is the boundary the
    three permitted transforms draw: anything none of them can reach is a gap.
    """

    term: str
    required: bool


@dataclass(frozen=True, slots=True)
class TailoredCv:
    """A CV rendered for one posting, with its own explanation.

    Attributes:
        markdown: The document. Single-column and heading-led, so it survives the
            parseability checks this project already applies to uploads.
        surfaced: What this posting pulled forward, and why.
        gaps: What it asks for that the profile cannot back.
        omitted_unevidenced: Skills left out for having no role behind them.
    """

    markdown: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)
    surfaced: tuple[Surfaced, ...] = field(default_factory=tuple)
    gaps: tuple[Gap, ...] = field(default_factory=tuple)
    omitted_unevidenced: tuple[str, ...] = field(default_factory=tuple)
    substitutions: tuple[Substitution, ...] = field(default_factory=tuple)


def _month_year(value: date) -> str:
    """Format a date the way parsers expect to find it.

    `Mar 2021` is one of the forms `analysis.parseability` names as machine-readable,
    which matters because the document this produces is checked by it.

    Args:
        value: The date.

    Returns:
        The month and year.
    """
    return f"{_MONTHS[value.month - 1]} {value.year}"


def _span(start: date | None, end: date | None) -> str:
    """Render a date range, treating an absent end as ongoing.

    Args:
        start: When it began.
        end: When it ended, or None for current.

    Returns:
        The range, or an empty string when neither date is known.
    """
    if start is None and end is None:
        return ""
    if start is None:
        return _month_year(end) if end else ""
    return f"{_month_year(start)} {_RANGE} {_month_year(end) if end else 'Present'}"


def _wanted(keywords: Sequence[Keyword]) -> dict[str, Keyword]:
    """Index a posting's keywords by canonical term.

    Args:
        keywords: What the posting asks for.

    Returns:
        Term to keyword.
    """
    return {keyword.term: keyword for keyword in keywords}


def _company_words(company: str | None) -> frozenset[str]:
    """Return the canonical forms of an employer's own name.

    A posting names its employer repeatedly, and the extractor cannot tell a company
    from a technology — `A.Team` looks exactly like a tool. Reporting the employer as a
    skill the user lacks is both wrong and slightly absurd, and the caller already knows
    which it is because the company is a stored field.

    Args:
        company: The hiring company, when known.

    Returns:
        Canonical forms to exclude from the gap list. Empty when no company is known.
    """
    if not company:
        return frozenset()
    parts = [company, *company.replace(".", " ").split()]
    return frozenset(canonical(part) for part in parts if part.strip())


def posting_spellings(job_description: str) -> dict[str, str]:
    """Map each canonical term to the spelling the posting actually used.

    `extract_keywords` returns canonical forms, which is right for comparing and wrong
    for quoting: a posting saying `PostgreSQL` and one saying `Postgres` are the same
    term and not the same word. Transform 2 needs the word.

    Args:
        job_description: The posting text.

    Returns:
        Canonical term to the posting's first spelling of it.
    """
    spellings: dict[str, str] = {}
    for match in _SPELLING.finditer(job_description):
        word = match.group(0).rstrip("./-")
        if word:
            spellings.setdefault(canonical(word.casefold()), word)
    return spellings


def substitute(
    skill: SkillFact, spellings: dict[str, str]
) -> tuple[str, Substitution | None]:
    """Adopt the posting's wording for a skill, where the alias map says it may.

    **Transform 2, and the whole of its safety argument.** Substitution is only sound
    because something authoritative asserts two spellings name one thing. Here that
    something is `SKILL_ALIASES`, 37 hand-curated software terms — so the gate is not
    "do these resolve to the same canonical form", which coincidence can satisfy, but
    "**did the alias map put them there**".

    That is also how PLANNING's requirement to *disable* this outside software is met
    without needing to detect the user's occupation. There is no equivalence data for
    nursing or accountancy, so the map never asserts anything about them, so no
    substitution ever fires. A profile outside software gets its own words back,
    unchanged, with no special case anywhere in the code.

    Args:
        skill: The profile's skill.
        spellings: The posting's own spellings, by canonical term.

    Returns:
        The wording to render, and the substitution when one was made.
    """
    theirs = spellings.get(skill.canonical_name)
    if theirs is None or theirs.casefold() == skill.name.casefold():
        return skill.name, None

    # Both sides must have been routed through the alias map: equal after casefolding
    # is not an equivalence anyone asserted.
    mine = skill.name.casefold()
    if mine not in SKILL_ALIASES and theirs.casefold() not in SKILL_ALIASES:
        return skill.name, None

    return theirs, Substitution(
        from_term=skill.name, to_term=theirs, via=skill.canonical_name
    )


def _rank(skill: SkillFact, wanted: dict[str, Keyword]) -> tuple[int, float, str]:
    """Sort key placing the skills this posting asks for first.

    Args:
        skill: The skill to rank.
        wanted: The posting's terms.

    Returns:
        A key ordering asked-for skills ahead of the rest, heaviest first, then
        alphabetically so the output is stable for a given profile and posting.
    """
    keyword = wanted.get(skill.canonical_name)
    if keyword is None:
        return (1, 0.0, skill.name.casefold())
    return (0, -keyword.weight, skill.name.casefold())


def tailor(
    facts: ProfileFacts, job_description: str, *, company: str | None = None
) -> TailoredCv:
    """Render the profile as a CV aimed at one posting.

    Args:
        facts: The profile, as the only permitted source of content.
        job_description: The posting text.
        company: The hiring company, used only to keep its own name out of the gap
            list. A posting repeats the employer's name throughout, and the extractor
            has no way to know `A.Team` is a company rather than a technology — but the
            caller does, because it is a stored field.

    Returns:
        The document, what was surfaced, and what is missing.
    """
    keywords = extract_keywords(job_description)
    wanted = _wanted(keywords)

    evidenced = [skill for skill in facts.skills if skill.evidenced_by]
    omitted = tuple(
        sorted(skill.name for skill in facts.skills if not skill.evidenced_by)
    )
    ordered = sorted(evidenced, key=lambda skill: _rank(skill, wanted))

    # Transform 2, applied once per skill so the document and the report agree about
    # every word. A skill the alias map has never heard of comes back unchanged.
    spellings = posting_spellings(job_description)
    rendered: list[tuple[SkillFact, str]] = []
    substitutions: list[Substitution] = []
    for skill in ordered:
        word, made = substitute(skill, spellings)
        rendered.append((skill, word))
        if made is not None:
            substitutions.append(made)

    words = {skill.canonical_name: word for skill, word in rendered}
    by_id = {experience.id: experience for experience in facts.experiences}
    surfaced = tuple(
        Surfaced(
            term=skill.canonical_name,
            required=wanted[skill.canonical_name].required,
            skill=words[skill.canonical_name],
            evidence=tuple(
                f"{by_id[experience_id].title}, {by_id[experience_id].organisation}"
                for experience_id in sorted(skill.evidenced_by)
                if experience_id in by_id
            ),
        )
        for skill in ordered
        if skill.canonical_name in wanted
    )

    covered = {skill.canonical_name for skill in evidenced}
    ignored = _company_words(company)
    # What the posting asks for and no role can back, in `extract_keywords` order so
    # the gap list agrees with the coverage report. Capped: forty terms is a wall.
    gaps = tuple(
        Gap(term=keyword.term, required=keyword.required)
        for keyword in keywords
        if keyword.term not in covered and keyword.term not in ignored
    )[:DEFAULT_MAX_REPORTED_GAPS]

    blocks = _blocks(facts, rendered, wanted)
    return TailoredCv(
        markdown=render_markdown(blocks),
        blocks=blocks,
        surfaced=surfaced,
        gaps=gaps,
        omitted_unevidenced=omitted,
        substitutions=tuple(substitutions),
    )


def _blocks(
    facts: ProfileFacts,
    rendered: Sequence[tuple[SkillFact, str]],
    wanted: dict[str, Keyword],
) -> tuple[Block, ...]:
    """Lay the facts out as a sequence of semantic blocks.

    One document model, because there are two renderers and there will be more.
    Building Markdown and then parsing it back to produce a DOCX would make the
    Markdown a private interchange format, which is how a formatting change in one
    output silently breaks the other.

    Single column, one heading per section, dates in a named-month form, no tables and
    no columns — the shapes `analysis.parseability` reports as lost. Section names are
    the literal words `EXPECTED_SECTIONS` looks for, so the generator and the checker
    cannot drift apart.

    Args:
        facts: The profile.
        rendered: Evidenced skills in this posting's order, each with the wording to use
            — which is the user's own unless transform 2 substituted the posting's.
        wanted: The posting's terms, for choosing what to surface per role.

    Returns:
        The document.
    """
    blocks: list[Block] = [
        Block(BlockKind.NAME, facts.full_name or facts.headline or "Curriculum Vitae")
    ]
    if facts.full_name and facts.headline:
        blocks.append(Block(BlockKind.HEADLINE, facts.headline))

    contact = [
        part
        for part in (
            facts.location,
            facts.email,
            facts.phone,
            facts.linkedin_url,
            facts.website_url,
        )
        if part
    ]
    if contact:
        blocks.append(Block(BlockKind.CONTACT, _SEPARATOR.join(contact)))

    if facts.summary:
        blocks += [
            Block(BlockKind.SECTION, "Summary"),
            Block(BlockKind.BODY, facts.summary),
        ]

    if rendered:
        blocks += [
            Block(BlockKind.SECTION, "Skills"),
            Block(BlockKind.BODY, ", ".join(word for _, word in rendered)),
        ]

    if facts.experiences:
        blocks.append(Block(BlockKind.SECTION, "Experience"))
        for experience in facts.experiences:
            blocks.append(
                Block(
                    BlockKind.ENTRY,
                    f"{experience.title}, {experience.organisation}",
                )
            )
            meta = [
                part
                for part in (
                    _span(experience.start_date, experience.end_date),
                    experience.location,
                )
                if part
            ]
            if meta:
                blocks.append(Block(BlockKind.META, _SEPARATOR.join(meta)))
            if experience.description:
                blocks.append(Block(BlockKind.BODY, experience.description))

            # The surface transform, where it shows: skills this role evidences that
            # the posting asked for.
            relevant = [
                word
                for skill, word in rendered
                if experience.id in skill.evidenced_by
                and skill.canonical_name in wanted
            ][:DEFAULT_MAX_SURFACED_SKILLS_PER_ROLE]
            if relevant:
                blocks.append(
                    Block(BlockKind.BODY, f"{_RELEVANT_LABEL}{', '.join(relevant)}")
                )

    if facts.educations:
        blocks.append(Block(BlockKind.SECTION, "Education"))
        for education in facts.educations:
            blocks.append(
                Block(
                    BlockKind.ENTRY,
                    f"{education.qualification}, {education.institution}",
                )
            )
            meta = [
                part
                for part in (
                    _span(education.start_date, education.end_date),
                    education.field_of_study,
                    education.grade,
                )
                if part
            ]
            if meta:
                blocks.append(Block(BlockKind.META, _SEPARATOR.join(meta)))

    return tuple(blocks)


_MARKDOWN_PREFIX: dict[BlockKind, str] = {
    BlockKind.NAME: "# ",
    BlockKind.SECTION: "## ",
    BlockKind.ENTRY: "### ",
}


def render_markdown(blocks: Sequence[Block]) -> str:
    """Render the document as Markdown.

    Args:
        blocks: The document.

    Returns:
        Markdown, one blank line between blocks.
    """
    body = "\n\n".join(
        f"{_MARKDOWN_PREFIX.get(block.kind, '')}{block.text}" for block in blocks
    )
    return body.strip() + "\n"


def content_values(facts: ProfileFacts) -> set[str]:
    """Return every string the generator is permitted to emit.

    Exists for the grounding test rather than for production: it is the definition of
    "traces to a profile fact", written once so the test cannot drift from the renderer
    by restating it in its own words.

    Args:
        facts: The profile.

    Returns:
        Every user-supplied value on the profile.
    """
    values = {
        value
        for value in (
            facts.full_name,
            facts.email,
            facts.headline,
            facts.summary,
            facts.location,
            facts.website_url,
            facts.linkedin_url,
        )
        if value
    }
    for experience in facts.experiences:
        values.update(
            value
            for value in (
                experience.title,
                experience.organisation,
                experience.location,
                experience.description,
            )
            if value
        )
    for education in facts.educations:
        values.update(
            value
            for value in (
                education.institution,
                education.qualification,
                education.field_of_study,
                education.grade,
            )
            if value
        )
    values.update(skill.name for skill in facts.skills)
    return values


__all__ = [
    "EducationFact",
    "ExperienceFact",
    "Gap",
    "ProfileFacts",
    "SkillFact",
    "Surfaced",
    "TailoredCv",
    "canonical",
    "content_values",
    "tailor",
]
