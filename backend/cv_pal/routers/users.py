from fastapi import APIRouter, status

from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.schemas import AccountDelete, AccountUpdate, PasswordChange, UserResponse
from cv_pal.services import user_service

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
    payload: PasswordChange, current_user: CurrentUser, db: DbSession
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

    Raises:
        AuthenticationError: If the current password is wrong.
    """
    await user_service.change_password(
        db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


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
    payload: AccountDelete, current_user: CurrentUser, db: DbSession
) -> None:
    """Delete the account, its profile, its CVs and the files behind them.

    Irreversible: principle 4 says the user owns their data, and data the operator can
    still restore has not been deleted.

    Args:
        payload: The account's password, as confirmation.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        AuthenticationError: If the password is wrong.
    """
    await user_service.delete_account(db, user=current_user, password=payload.password)
