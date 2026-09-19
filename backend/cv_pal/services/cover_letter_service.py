"""Drafting and keeping cover letters.

Generation is deterministic and needs no model; the letter is assembled from profile
facts by `generation.cover_letter`. What this module adds is the part that needs a
database: **the self-similarity check, which is meaningless without a corpus of the
user's own earlier letters.**

The two halves are deliberately not one call. Generating a draft measures it against
what the user has *kept*, not against every draft they ever previewed — otherwise the
number would drift upward every time they pressed the button and would stop meaning
anything.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.analysis.similarity import SimilarityResult, self_similarity
from cv_pal.constants import DEFAULT_SIMILARITY_CORPUS_SIZE
from cv_pal.generation.cover_letter import CoverLetterDraft, compose, contains_prompt
from cv_pal.generation.tailored_cv import tailor
from cv_pal.models import CoverLetter, JobPosting, User
from cv_pal.services.job_service import get_posting
from cv_pal.services.profile_service import get_or_create_profile
from cv_pal.services.tailoring_service import profile_facts


async def _recent_bodies(
    db: AsyncSession, *, user_id: int, exclude_posting_id: int
) -> list[str]:
    """Return the user's kept letters, newest first.

    The letter for *this* posting is excluded: comparing a redraft against its own
    saved version measures how much the user changed their mind, not whether they send
    the same letter to everyone.

    Args:
        db: Async database session.
        user_id: The owning user.
        exclude_posting_id: The posting being drafted for.

    Returns:
        Letter bodies, newest first, capped.
    """
    result = await db.execute(
        select(CoverLetter.body)
        .where(
            CoverLetter.user_id == user_id,
            CoverLetter.job_posting_id != exclude_posting_id,
        )
        .order_by(CoverLetter.updated_at.desc())
        .limit(DEFAULT_SIMILARITY_CORPUS_SIZE)
    )
    return list(result.scalars().all())


async def draft_for_posting(
    db: AsyncSession, *, user: User, posting_id: int
) -> tuple[CoverLetterDraft, SimilarityResult, JobPosting]:
    """Assemble a letter for one posting and measure it against the user's own.

    The evidence lines are taken from the tailored CV's `surfaced` list rather than
    recomputed, so the letter and the CV can never disagree about which requirements
    the user evidences — a disagreement the reader would be the first to notice.

    Args:
        db: Async database session.
        user: The owning account.
        posting_id: The posting to write to.

    Returns:
        The draft, its similarity to earlier letters, and the posting.

    Raises:
        PostingNotFoundError: If the posting does not exist for this user.
    """
    posting = await get_posting(db, user_id=user.id, posting_id=posting_id)
    profile = await get_or_create_profile(db, user_id=user.id)
    facts = profile_facts(profile, user)

    tailored = tailor(facts, posting.description, company=posting.company)
    draft = compose(
        facts,
        job_title=posting.title,
        company=posting.company,
        surfaced=tailored.surfaced,
    )

    previous = await _recent_bodies(db, user_id=user.id, exclude_posting_id=posting_id)
    return draft, self_similarity(draft.body, previous), posting


async def save_letter(
    db: AsyncSession, *, user: User, posting_id: int, body: str
) -> tuple[CoverLetter, SimilarityResult, bool]:
    """Keep a letter against a posting, replacing any previous one.

    The similarity is recomputed against **the text being saved**, not against the
    generated draft: the edited version is what would be sent, and it is the only one
    worth measuring.

    Args:
        db: Async database session.
        user: The owning account.
        posting_id: The posting the letter is for.
        body: The letter, as edited.

    Returns:
        The stored letter, its similarity to the user's others, and whether the
        unwritten-paragraph prompt is still in it.

    Raises:
        PostingNotFoundError: If the posting does not exist for this user.
    """
    await get_posting(db, user_id=user.id, posting_id=posting_id)

    previous = await _recent_bodies(db, user_id=user.id, exclude_posting_id=posting_id)
    similarity = self_similarity(body, previous)

    existing = await db.execute(
        select(CoverLetter).where(
            CoverLetter.user_id == user.id,
            CoverLetter.job_posting_id == posting_id,
        )
    )
    letter = existing.scalar_one_or_none()
    if letter is None:
        letter = CoverLetter(user_id=user.id, job_posting_id=posting_id, body=body)
        db.add(letter)
    else:
        letter.body = body

    await db.commit()
    await db.refresh(letter)
    return letter, similarity, contains_prompt(body)


__all__ = ["draft_for_posting", "save_letter"]
