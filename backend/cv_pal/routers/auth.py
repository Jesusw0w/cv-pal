from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from cv_pal.auth import (
    clear_session_cookies,
    get_user_by_email,
    set_session_cookies,
    wants_cookie_session,
)
from cv_pal.config import get_settings
from cv_pal.constants import (
    DEFAULT_ERROR_INVALID_CREDENTIALS,
    DEFAULT_REFRESH_COOKIE,
    DEFAULT_TOKEN_TYPE_COOKIE,
)
from cv_pal.dependencies import CurrentUser, DbSession
from cv_pal.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidRefreshTokenError,
    RegistrationClosedError,
)
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


def _presented_refresh_token(
    payload: RefreshRequest | None, request: Request
) -> str | None:
    """Find the refresh token in the body, or in the cookie of a cookie session.

    Args:
        payload: The request body, if one was sent.
        request: The incoming request.

    Returns:
        The token, or None when the client presented none.
    """
    if payload is not None:
        return payload.refresh_token
    if wants_cookie_session(request):
        return request.cookies.get(DEFAULT_REFRESH_COOKIE)
    return None


def _token_response(
    request: Request, response: Response, *, access: str, refresh: str
) -> Token:
    """Hand a token pair over in the body, or as cookies for a cookie session.

    Args:
        request: The incoming request.
        response: The outgoing response.
        access: The access token.
        refresh: The refresh token.

    Returns:
        The response body.
    """
    if wants_cookie_session(request):
        set_session_cookies(response, access=access, refresh=refresh)
        return Token(token_type=DEFAULT_TOKEN_TYPE_COOKIE)
    return Token(access_token=access, refresh_token=refresh)


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
    form_data: LoginForm,
    request: Request,
    response: Response,
    db: DbSession,
    limiter: Limiter,
) -> Token:
    """Authenticate and issue a token pair.

    Args:
        form_data: OAuth2 form carrying the email as ``username`` and the password.
        request: The incoming request, used for rate limiting and the session mode.
        response: The outgoing response, for session cookies.
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
    return _token_response(
        request, response, access=access_token, refresh=refresh_token
    )


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    limiter: Limiter,
    payload: RefreshRequest | None = None,
) -> Token:
    """Exchange a refresh token for a new token pair.

    Refresh tokens are single-use: the presented token is revoked and replaced. If an
    already-revoked token is presented, every session for that user is revoked, on the
    basis that two parties cannot both legitimately hold the same one-time token.

    Args:
        request: The incoming request, used for rate limiting and the session mode.
        response: The outgoing response, for session cookies.
        db: Async database session.
        limiter: Request throttling.
        payload: The refresh token to exchange; omitted in a cookie session.

    Returns:
        A new access and refresh token pair.

    Raises:
        RateLimitedError: If this client has refreshed too often.
        InvalidRefreshTokenError: If the token is unknown, expired or revoked.
    """
    limiter.check(client_key(request, "refresh"))

    token = _presented_refresh_token(payload, request)
    if token is None:
        raise InvalidRefreshTokenError

    access_token, refresh_token = await auth_service.rotate_refresh_token(
        db, token=token
    )
    return _token_response(
        request, response, access=access_token, refresh=refresh_token
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    payload: RefreshRequest | None = None,
) -> None:
    """End the session belonging to a refresh token, from the body or the cookie.

    Succeeds whether or not the token was valid: the caller's intent is satisfied
    either way, and distinguishing the cases would confirm which tokens exist.
    """
    token = _presented_refresh_token(payload, request)
    if token is not None:
        await auth_service.revoke_refresh_token(db, token=token)
    clear_session_cookies(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: CurrentUser, db: DbSession, response: Response
) -> None:
    """End every session for the authenticated user, on all devices."""
    await auth_service.revoke_all_sessions(db, user_id=current_user.id)
    clear_session_cookies(response)
