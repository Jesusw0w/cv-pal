"""Complement the deterministic CV read with a language model, when one answers.

`extraction` is the floor: it runs everywhere, costs nothing and never changes its
answer. It is also a pattern matcher, and it loses whatever the pattern did not
anticipate — most visibly a role's bullet points, which it flattens into one line, and
the layout that puts a date range at the end of the heading instead of an em dash.

This raises the floor where a model is configured. Same contract as everything else on
the import path: **a proposal, never a write.** Nothing here persists anything, and the
user confirms each record through the ordinary profile endpoints.

The merge keeps the deterministic result wherever the two overlap on a fact a regular
expression is simply better at — the email, the phone number, the links. Roles and
courses are taken from the model when it found any, as a whole list rather than field by
field: interleaving two readings of the same CV produces near-duplicate rows, and asking
someone to spot which of two similar entries is the right one is worse than showing them
one that is occasionally wrong.
"""

import logging
from datetime import date

from cv_pal.analysis.extraction import ExtractedEntry, ExtractedProfile, is_education
from cv_pal.analysis.keywords import canonical
from cv_pal.constants import (
    DEFAULT_LOCATION_MAX_LENGTH,
    DEFAULT_MAX_IMPORTED_SKILLS,
    DEFAULT_ORGANISATION_MAX_LENGTH,
    DEFAULT_SKILL_NAME_MAX_LENGTH,
    DEFAULT_SUMMARY_MAX_LENGTH,
    DEFAULT_TITLE_MAX_LENGTH,
)
from cv_pal.exceptions import LLMError
from cv_pal.llm import LLMClient, complete_validated
from cv_pal.prompts import (
    CV_IMPORT_RETRY_PROMPT,
    CV_IMPORT_SYSTEM_PROMPT,
    CV_IMPORT_USER_PROMPT,
)
from cv_pal.schemas import ImportedEntry, ImportedProfile

logger = logging.getLogger(__name__)


def _month(value: str | None, *, end_of_range: bool = False) -> date | None:
    """Read a ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD`` string as the first of its month.

    Args:
        value: The date as the model wrote it, already pattern-checked by the schema.
        end_of_range: Whether this is the closing date, which defaults to December
            rather than January so a year-only range spans the whole year — the same
            rule the deterministic pass applies.

    Returns:
        The date, or None when the model gave none.
    """
    if not value:
        return None
    parts = value.split("-")
    month = int(parts[1]) if len(parts) > 1 else (12 if end_of_range else 1)
    return date(int(parts[0]), month, 1)


def _entry(found: ImportedEntry) -> ExtractedEntry | None:
    """Convert one transcribed entry, or reject it.

    Args:
        found: An entry as the model returned it.

    Returns:
        The entry, or None when it names neither an organisation nor a title — a row
        with nothing in it costs the user a line to read and a click to dismiss.
    """
    organisation = found.organisation.strip()
    title = found.title.strip()
    if not organisation or not title:
        return None

    # Bullets are kept one per line. That is what the profile editor shows, and what
    # someone pastes into a job board that asks for a role's responsibilities.
    highlights = [line.strip(" -•·") for line in found.highlights]
    description = "\n".join(line for line in highlights if line)

    location = (found.location or "").strip()
    return ExtractedEntry(
        organisation=organisation[:DEFAULT_ORGANISATION_MAX_LENGTH],
        title=title[:DEFAULT_TITLE_MAX_LENGTH],
        location=location[:DEFAULT_LOCATION_MAX_LENGTH] or None,
        start_date=_month(found.start),
        end_date=_month(found.end, end_of_range=True),
        description=description or None,
    )


def _entries(found: list[ImportedEntry]) -> tuple[ExtractedEntry, ...]:
    """Convert transcribed entries, dropping the ones with nothing in them.

    Args:
        found: Entries as the model returned them.

    Returns:
        The usable entries, in the order given.
    """
    converted = (_entry(item) for item in found)
    return tuple(entry for entry in converted if entry is not None)


def _skills(base: tuple[str, ...], found: list[str]) -> tuple[str, ...]:
    """Union the two skill lists, deduplicated by canonical form.

    The deterministic pass proposes only terms its vocabulary already knows, which is
    the right rule when the alternative is accepting sentence fragments. A model reading
    the skills section does not have that problem, so its terms are taken as written —
    capped, because an unbounded list is a wall of chips nobody reads.

    Args:
        base: What the deterministic pass proposed, already canonical.
        found: What the model read, in the CV's own spelling.

    Returns:
        The deterministic terms first, then whatever the model added.
    """
    seen = {canonical(name) for name in base}
    merged = list(base)
    for raw in found:
        name = raw.strip()[:DEFAULT_SKILL_NAME_MAX_LENGTH]
        key = canonical(name)
        if not name or key in seen:
            continue
        seen.add(key)
        merged.append(name)
    return tuple(merged[:DEFAULT_MAX_IMPORTED_SKILLS])


def merge(base: ExtractedProfile, found: ImportedProfile) -> ExtractedProfile:
    """Combine the deterministic read with the model's transcription.

    Args:
        base: What the deterministic pass found.
        found: What the model transcribed.

    Returns:
        The combined proposal, marked as enriched.
    """
    entries = _entries(found.experiences) + _entries(found.educations)
    # Classified by content rather than by which list the model put them in: it is the
    # rule the deterministic pass already uses, and it costs nothing to apply here.
    experiences = tuple(entry for entry in entries if not is_education(entry))
    educations = tuple(entry for entry in entries if is_education(entry))

    written = (found.summary or "").strip()[:DEFAULT_SUMMARY_MAX_LENGTH]
    return ExtractedProfile(
        contact=base.contact,
        headline=base.headline,
        summary=base.summary or written or None,
        location=base.location,
        experiences=experiences or base.experiences,
        educations=educations or base.educations,
        skills=_skills(base.skills, found.skills),
        enriched=True,
    )


async def enrich(
    client: LLMClient, *, cv_text: str, base: ExtractedProfile
) -> ExtractedProfile | None:
    """Ask a model to transcribe the CV and merge what it read into the proposal.

    Failure is not an error here. The import already has a usable answer, so an
    unreachable provider, a model that never returns valid JSON, or no provider
    configured at all costs the user the richer read and nothing else.

    Args:
        client: The language model client.
        cv_text: The text extracted from the CV.
        base: The deterministic proposal to complement.

    Returns:
        The enriched proposal, or None when no model answered usably.
    """
    try:
        found = await complete_validated(
            client,
            system=CV_IMPORT_SYSTEM_PROMPT,
            user=CV_IMPORT_USER_PROMPT.format(cv_text=cv_text),
            schema=ImportedProfile,
            retry_prompt=CV_IMPORT_RETRY_PROMPT,
        )
    except LLMError:
        logger.info("CV import enrichment unavailable; returning deterministic read")
        return None
    return merge(base, found)
