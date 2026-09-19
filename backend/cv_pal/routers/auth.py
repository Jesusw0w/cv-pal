from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from cv_pal.auth import get_user_by_email
from cv_pal.config import get_settings
from cv_pal.constants import DEFAULT_ERROR_INVALID_CREDENTIALS
from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.exceptions import EmailAlreadyRegisteredError, RegistrationClosedError
from cv_pal.hashing import hash_password
from cv_pal.models import User
from cv_pal.rate_limit import RateLimiter, get_rate_limiter
from cv_pal.schemas import RefreshRequest, Token, UserCreate, UserResponse
from cv_pal.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]


def client_key(request: Request, endpoint: str) -> str:
    """Build the per-client rate-limit key for an endpoint.

    Args:
        request: The incoming request.
        endpoint: A short endpoint identifier.

    Returns:
        A key combining the endpoint and the client address.
    """
    host = request.client.host if request.client else "unknown"
    return f"{endpoint}:{host}"


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate, request: Request, db: DbSession, limiter: Limiter
) -> UserResponse:
    """Register a new user account.

    Args:
        user_in: Registration data (email, password, optional full name).
        request: The incoming request, used for rate limiting.
        db: Async database session.
        limiter: Request throttling.

    Returns:
        The created user profile.

    Raises:
        RegistrationClosedError: If this instance is not accepting new accounts.
        RateLimitedError: If this client has registered too many times recently.
        EmailAlreadyRegisteredError: If the email is already registered.
    """
    if not get_settings().allow_registration:
        raise RegistrationClosedError

    limiter.check(client_key(request, "register"))

    if await get_user_by_email(db, user_in.email) is not None:
        raise EmailAlreadyRegisteredError

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: LoginForm, request: Request, db: DbSession, limiter: Limiter
) -> Token:
    """Authenticate and return a JWT access token.

    Args:
        form_data: OAuth2 form carrying the email as ``username`` and the password.
        request: The incoming request, used for rate limiting.
        db: Async database session.
        limiter: Request throttling and failure backoff.

    Returns:
        A token for the authenticated user.

    Raises:
        RateLimitedError: If this client or this account has made too many attempts.
        HTTPException: 401 if the credentials are invalid.
    """
    limiter.check(client_key(request, "login"))

    user = await auth_service.authenticate(
        db, email=form_data.username, password=form_data.password, limiter=limiter
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=DEFAULT_ERROR_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token = await auth_service.issue_tokens(db, user=user)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshRequest, request: Request, db: DbSession, limiter: Limiter
) -> Token:
    """Exchange a refresh token for a new token pair.

    Refresh tokens are single-use: the presented token is revoked and replaced. If an
    already-revoked token is presented, every session for that user is revoked, on the
    basis that two parties cannot both legitimately hold the same one-time token.

    Args:
        payload: The refresh token to exchange.
        request: The incoming request, used for rate limiting.
        db: Async database session.
        limiter: Request throttling.

    Returns:
        A new access and refresh token pair.

    Raises:
        RateLimitedError: If this client has refreshed too often.
        InvalidRefreshTokenError: If the token is unknown, expired or revoked.
    """
    limiter.check(client_key(request, "refresh"))

    access_token, refresh_token = await auth_service.rotate_refresh_token(
        db, token=payload.refresh_token
    )
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: DbSession) -> None:
    """End the session belonging to a refresh token.

    Succeeds whether or not the token was valid: the caller's intent is satisfied
    either way, and distinguishing the cases would confirm which tokens exist.

    Args:
        payload: The refresh token to revoke.
        db: Async database session.
    """
    await auth_service.revoke_refresh_token(db, token=payload.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user: CurrentUser, db: DbSession) -> None:
    """End every session for the authenticated user, on all devices.

    Args:
        current_user: The authenticated user.
        db: Async database session.
    """
    await auth_service.revoke_all_sessions(db, user_id=current_user.id)
