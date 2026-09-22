from fastapi import APIRouter, Response, status

from cv_pal.auth import clear_session_cookies
from cv_pal.dependencies import CurrentUser, DbSession, SettingsDep
from cv_pal.schemas import (
    AccountDelete,
    AccountUpdate,
    ApiTokenCreate,
    ApiTokenCreatedResponse,
    ApiTokenListResponse,
    ApiTokenResponse,
    PasswordChange,
    UserResponse,
)
from cv_pal.services import api_token_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: CurrentUser) -> UserResponse:
    """Get the current authenticated user's profile.

    Returns:
        The user's profile data.
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_users_me(
    payload: AccountUpdate, current_user: CurrentUser, db: DbSession
) -> UserResponse:
    """Change the account's display name.

    The name heads every generated CV. Without this it could only be set at
    registration, where it is optional — so an account created without one produced
    documents titled "Curriculum Vitae" with no way to correct them.

    Args:
        payload: The new name, or null to clear it.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated account.
    """
    user = await user_service.update_account(
        db, user=current_user, full_name=payload.full_name
    )
    return UserResponse.model_validate(user)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: CurrentUser,
    db: DbSession,
    response: Response,
) -> None:
    """Change the account's password.

    Requires the current password as well as the bearer token, and ends **every**
    session including this one.

    There is no signed-out reset: that needs an SMTP server a self-hosted instance may
    not have. Locked out, use `python -m cv_pal.admin reset-password <email>`.

    Args:
        payload: The current password and the replacement.
        current_user: The authenticated user.
        db: Async database session.
        response: The outgoing response, to clear the now-dead session cookies.

    Raises:
        AuthenticationError: If the current password is wrong.
    """
    await user_service.change_password(
        db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    clear_session_cookies(response)


@router.get("/me/export")
async def export_users_me(
    current_user: CurrentUser, db: DbSession
) -> dict[str, object]:
    """Download everything the account holds, as JSON.

    The other half of principle 4: the delete below is irreversible, so there has to be
    a way to take a copy out first. Uploaded files are not inlined — they are downloaded
    whole from the documents endpoints.

    Returns:
        A snapshot of the account.
    """
    return await user_service.export_account(db, user=current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: AccountDelete,
    current_user: CurrentUser,
    db: DbSession,
    response: Response,
) -> None:
    """Delete the account, its profile, its CVs and the files behind them.

    Irreversible: principle 4 says the user owns their data, and data the operator can
    still restore has not been deleted.

    Args:
        payload: The account's password, as confirmation.
        current_user: The authenticated user.
        db: Async database session.
        response: The outgoing response, to clear the session cookies.

    Raises:
        AuthenticationError: If the password is wrong.
    """
    await user_service.delete_account(db, user=current_user, password=payload.password)
    clear_session_cookies(response)


@router.get("/me/tokens", response_model=ApiTokenListResponse)
async def list_tokens(
    current_user: CurrentUser, db: DbSession, settings: SettingsDep
) -> ApiTokenListResponse:
    """List the personal access tokens agents use to reach the MCP endpoint.

    Returns:
        The live and expired tokens, and whether the endpoint is enabled at all.
    """
    tokens = await api_token_service.list_tokens(db, user_id=current_user.id)
    return ApiTokenListResponse(
        mcp_enabled=settings.mcp_enabled,
        tokens=[ApiTokenResponse.model_validate(token) for token in tokens],
    )


@router.post(
    "/me/tokens",
    response_model=ApiTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    payload: ApiTokenCreate, current_user: CurrentUser, db: DbSession
) -> ApiTokenCreatedResponse:
    """Issue a personal access token. The secret is in this response and nowhere else.

    Args:
        payload: Its name, scope, lifetime, and the account's password.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The token, including its secret.

    Raises:
        AuthenticationError: If the password is wrong.
        ConflictError: If the user already holds the maximum number of tokens.
    """
    token, plaintext = await api_token_service.create_token(
        db,
        user=current_user,
        password=payload.password,
        name=payload.name,
        write=payload.write,
        expires_in_days=payload.expires_in_days,
    )
    return ApiTokenCreatedResponse(
        **ApiTokenResponse.model_validate(token).model_dump(), token=plaintext
    )


@router.delete("/me/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(token_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Revoke a personal access token. Any agent using it is cut off at once.

    Args:
        token_id: The token to revoke.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        NotFoundError: If the user has no such token.
    """
    await api_token_service.revoke_token(db, user_id=current_user.id, token_id=token_id)
