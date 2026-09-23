"""Tailoring a CV to a saved posting.

The one place the ORM meets the generator. `generation.tailored_cv` is deliberately
pure and knows nothing about the database — this module loads the rows, snapshots them
into `ProfileFacts`, and hands over. Anything the snapshot does not carry is something
the generator cannot possibly emit, which is how *never fabricate experience* is
enforced by structure rather than by review.

Nothing is stored. The result is a deterministic function of the profile and the
posting, with no model involved, so recomputing on request is cheaper than keeping a
copy in step — the same reasoning that makes match scores read-time (see
`routers/jobs.list_jobs`). Phase 9 needs the exact document that was *sent* with an
application, and that is a different record with a different lifetime; it belongs to the
application, not here.
"""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.analysis.parseability import ParseabilityReport, check_parseability
from cv_pal.constants import DEFAULT_DOWNLOAD_NAME_MAX_LENGTH
from cv_pal.generation.tailored_cv import (
    EducationFact,
    ExperienceFact,
    ProfileFacts,
    SkillFact,
    TailoredCv,
    tailor,
)
from cv_pal.models import CareerProfile, User
from cv_pal.services.job_service import get_posting
from cv_pal.services.profile_service import get_or_create_profile

# An allowlist, not a denylist: anything outside letters, digits, spaces and a few
# harmless separators is replaced. A denylist is the version that misses one.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9 ._()-]+")


def profile_facts(profile: CareerProfile, user: User) -> ProfileFacts:
    """Snapshot the profile into the only shape the generator can read.

    Args:
        profile: The user's career profile, with its relationships loaded.
        user: The account, for the name and email the profile does not hold.

    Returns:
        The facts.
    """
    return ProfileFacts(
        full_name=user.full_name,
        # Parseability treats a missing email as an error, and the profile has no
        # email field — the account's is the only one there is.
        email=user.email,
        headline=profile.headline,
        summary=profile.summary,
        location=profile.location,
        phone=profile.phone,
        website_url=profile.website_url,
        github_url=profile.github_url,
        linkedin_url=profile.linkedin_url,
        experiences=tuple(
            ExperienceFact(
                id=experience.id,
                title=experience.title,
                organisation=experience.organisation,
                start_date=experience.start_date,
                end_date=experience.end_date,
                location=experience.location,
                description=experience.description,
            )
            for experience in profile.experiences
        ),
        educations=tuple(
            EducationFact(
                institution=education.institution,
                qualification=education.qualification,
                field_of_study=education.field_of_study,
                start_date=education.start_date,
                end_date=education.end_date,
                grade=education.grade,
            )
            for education in profile.educations
        ),
        skills=tuple(
            SkillFact(
                name=skill.name,
                canonical_name=skill.canonical_name,
                evidenced_by=frozenset(experience.id for experience in skill.evidence),
            )
            for skill in profile.skills
        ),
    )


def download_name(company: str | None, title: str, *, suffix: str) -> str:
    """Build a safe download filename for a tailored document.

    **Sanitised rather than trusted.** Both parts originate in a third-party job board,
    and this string ends up in a `Content-Disposition` header and then as a filename on
    the user's disk. A quote or a newline there is header injection; a slash or `..` is
    a path the browser may interpret. So the value is rebuilt from an allowlist instead
    of having the dangerous characters removed from it — a denylist is the version that
    misses one.

    Args:
        company: The hiring company, when known.
        title: The posting's title.
        suffix: The file extension, including the dot.

    Returns:
        A filename safe to put in a header, never empty.
    """
    parts = [part for part in (company, title) if part and part.strip()]
    stem = _UNSAFE_FILENAME.sub(" ", " - ".join(parts)).strip()
    stem = " ".join(stem.split())[:DEFAULT_DOWNLOAD_NAME_MAX_LENGTH].strip()
    return f"CV - {stem}{suffix}" if stem else f"CV{suffix}"


async def tailor_for_posting(
    db: AsyncSession, *, user: User, posting_id: int
) -> tuple[TailoredCv, ParseabilityReport]:
    """Render the user's profile as a CV aimed at one of their saved postings.

    The document is passed through the project's **own** parseability checker before it
    is returned. Generating a CV that the same application would flag on upload would be
    the sharpest possible inconsistency, and running the check here means it cannot
    happen quietly — the caller sees the same report it would see for a file.

    Args:
        db: Async database session.
        user: The owning account.
        posting_id: The posting to aim at.

    Returns:
        The tailored CV and the parseability report for it.

    Raises:
        PostingNotFoundError: If the posting does not exist for this user.
    """
    posting = await get_posting(db, user_id=user.id, posting_id=posting_id)
    profile = await get_or_create_profile(db, user_id=user.id)

    result = tailor(
        profile_facts(profile, user),
        posting.description,
        company=posting.company,
        title=posting.title,
    )
    return result, check_parseability(result.markdown)


__all__ = ["download_name", "profile_facts", "tailor_for_posting"]
