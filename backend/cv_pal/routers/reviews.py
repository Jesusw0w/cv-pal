from fastapi import APIRouter, status

from cv_pal.dependencies import CurrentUser, DbSession, LLMClientDep
from cv_pal.schemas import SuggestionResponse, SuggestionUpdate
from cv_pal.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post(
    "/cvs/{cv_id}/analyze",
    response_model=list[SuggestionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def analyze_cv(
    cv_id: int,
    current_user: CurrentUser,
    db: DbSession,
    client: LLMClientDep,
) -> list[SuggestionResponse]:
    """Analyse a CV and generate improvement suggestions.

    Args:
        cv_id: The ID of the CV to analyse.
        current_user: The authenticated user.
        db: Async database session.
        client: The configured language model client.

    Returns:
        The generated suggestions.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
        LLMError: If the model is unreachable or its output is unusable.
    """
    suggestions = await review_service.analyze_cv(
        db, cv_id=cv_id, user_id=current_user.id, client=client
    )
    return [SuggestionResponse.model_validate(s) for s in suggestions]


@router.get("/cvs/{cv_id}/suggestions", response_model=list[SuggestionResponse])
async def get_suggestions(
    cv_id: int, current_user: CurrentUser, db: DbSession
) -> list[SuggestionResponse]:
    """Get all suggestions recorded for a CV.

    Args:
        cv_id: The ID of the CV.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The CV's suggestions.

    Raises:
        CVNotFoundError: If the CV does not exist or belongs to another user.
    """
    suggestions = await review_service.list_suggestions(
        db, cv_id=cv_id, user_id=current_user.id
    )
    return [SuggestionResponse.model_validate(s) for s in suggestions]


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
async def update_suggestion(
    suggestion_id: int,
    update: SuggestionUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> SuggestionResponse:
    """Accept or reject a suggestion.

    Args:
        suggestion_id: The ID of the suggestion to update.
        update: The new acceptance state.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated suggestion.

    Raises:
        SuggestionNotFoundError: If the suggestion does not exist or belongs to
            another user.
    """
    suggestion = await review_service.set_suggestion_accepted(
        db,
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        accepted=update.accepted,
    )
    return SuggestionResponse.model_validate(suggestion)
