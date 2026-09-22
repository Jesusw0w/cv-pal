from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.auth import decode_token, get_user_by_email, wants_cookie_session
from cv_pal.config import Settings, get_settings
from cv_pal.constants import (
    DEFAULT_ACCESS_COOKIE,
    DEFAULT_ERROR_INACTIVE_USER,
    DEFAULT_ERROR_UNAUTHORIZED,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)
from cv_pal.database import get_db
from cv_pal.llm import LLMClient, get_llm_client
from cv_pal.models import User

# auto_error off: a browser session carries its token in a cookie, not the header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
BearerToken = Annotated[str | None, Depends(oauth2_scheme)]
# Declared here rather than per router, so the two endpoints that use a model resolve
# the same dependency — which is also the one the tests override with a fake.
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]


async def get_current_user(
    bearer: BearerToken, request: Request, db: DbSession
) -> User:
    """Resolve the authenticated user from a bearer token or the session cookie.

    The cookie only counts alongside the session header, which a cross-site form
    cannot send — that is what stops a forged request riding on the cookie.

    Args:
        bearer: The JWT from the Authorization header, if any.
        request: The incoming request, for the session cookie.
        db: Async database session.

    Returns:
        The authenticated ``User`` ORM instance.

    Raises:
        HTTPException: 401 if the token is invalid, the user no longer exists, or the
            account is inactive.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=DEFAULT_ERROR_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = bearer
    if token is None and wants_cookie_session(request):
        token = request.cookies.get(DEFAULT_ACCESS_COOKIE)
    if token is None:
        raise unauthorized

    payload = decode_token(token)
    if payload is None:
        raise unauthorized

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise unauthorized

    user = await get_user_by_email(db, subject)
    # A deleted account must not be distinguishable from a forged token.
    if user is None or payload.get("ver") != user.token_version:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DEFAULT_ERROR_INACTIVE_USER,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide an HTTP client for reading job boards.

    One client per request rather than one per process: this is only used on the
    import-a-link path, so a pool held open for the life of the application would be
    idle almost always. Overridden in tests with a transport that never touches the
    network.

    Yields:
        An async HTTP client.
    """
    async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as client:
        yield client


HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
