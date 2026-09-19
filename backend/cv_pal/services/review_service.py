import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.constants import DEFAULT_SUGGESTION_COUNT
from cv_pal.exceptions import SuggestionNotFoundError
from cv_pal.llm import LLMClient, complete_validated
from cv_pal.models import CV, Suggestion
from cv_pal.parsing import extract_cv_text
from cv_pal.prompts import (
    CV_ANALYSIS_RETRY_PROMPT,
    CV_ANALYSIS_SYSTEM_PROMPT,
    CV_ANALYSIS_USER_PROMPT,
)
from cv_pal.schemas import GeneratedSuggestions
from cv_pal.services.cv_service import get_owned_cv

logger = logging.getLogger(__name__)


async def _generate_suggestions(
    client: LLMClient, cv_text: str
) -> GeneratedSuggestions:
    """Ask the model for suggestions and validate its response.

    Args:
        client: The language model client.
        cv_text: The extracted CV text to analyse.

    Returns:
        The validated suggestions.

    Raises:
        LLMResponseError: If the model's output fails validation twice.
        LLMError: If the provider is unreachable.
    """
    return await complete_validated(
        client,
        system=CV_ANALYSIS_SYSTEM_PROMPT,
        user=CV_ANALYSIS_USER_PROMPT.format(
            cv_text=cv_text, max_suggestions=DEFAULT_SUGGESTION_COUNT
        ),
        schema=GeneratedSuggestions,
        retry_prompt=CV_ANALYSIS_RETRY_PROMPT,
    )


async def analyze_cv(
    db: AsyncSession, *, cv_id: int, user_id: int, client: LLMClient
) -> list[Suggestion]:
    """Analyse a CV and persist the resulting suggestions.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV to analyse.
        user_id: Identifier of the owning user.
        client: The language model client to use.

    Returns:
        The persisted suggestions.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
        UnsupportedFileTypeError: If the stored file cannot be parsed.
        LLMError: If the model is unreachable or its output is unusable.
    """
    cv = await get_owned_cv(db, cv_id=cv_id, user_id=user_id)
    cv_text = await extract_cv_text(Path(cv.file_path))
    generated = await _generate_suggestions(client, cv_text)

    suggestions = [
        Suggestion(cv_id=cv.id, suggestion_type=item.type, content=item.content)
        for item in generated.suggestions
    ]
    db.add_all(suggestions)
    await db.commit()
    for suggestion in suggestions:
        await db.refresh(suggestion)
    return suggestions


async def list_suggestions(
    db: AsyncSession, *, cv_id: int, user_id: int
) -> list[Suggestion]:
    """List the suggestions recorded for a CV.

    Args:
        db: Async database session.
        cv_id: Identifier of the CV.
        user_id: Identifier of the owning user.

    Returns:
        The CV's suggestions, oldest first.

    Raises:
        CVNotFoundError: If no such CV exists for this user.
    """
    await get_owned_cv(db, cv_id=cv_id, user_id=user_id)
    result = await db.execute(
        select(Suggestion).where(Suggestion.cv_id == cv_id).order_by(Suggestion.id)
    )
    return list(result.scalars().all())


async def set_suggestion_accepted(
    db: AsyncSession, *, suggestion_id: int, user_id: int, accepted: bool
) -> Suggestion:
    """Accept or reject a suggestion.

    Args:
        db: Async database session.
        suggestion_id: Identifier of the suggestion.
        user_id: Identifier of the owning user.
        accepted: Whether the suggestion is accepted.

    Returns:
        The updated suggestion.

    Raises:
        SuggestionNotFoundError: If the suggestion does not exist or belongs to a CV
            owned by another user.
    """
    # Ownership is enforced through the join, so another user's suggestion simply
    # does not exist as far as this caller is concerned.
    result = await db.execute(
        select(Suggestion)
        .join(CV, CV.id == Suggestion.cv_id)
        .where(Suggestion.id == suggestion_id, CV.user_id == user_id)
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise SuggestionNotFoundError

    suggestion.accepted = accepted
    await db.commit()
    await db.refresh(suggestion)
    return suggestion
