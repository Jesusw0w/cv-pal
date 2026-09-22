"""What the MCP server reaches out of process for, gathered so tests can swap it.

FastAPI's dependency overrides do not reach a mounted ASGI app, so the MCP side takes
its database, HTTP client and settings from here instead.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.config import Settings, get_settings
from cv_pal.constants import DEFAULT_HTTP_TIMEOUT_SECONDS
from cv_pal.database import async_session
from cv_pal.services import api_token_service
from cv_pal.services.api_token_service import ResolvedToken


@asynccontextmanager
async def _http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Open an HTTP client for reading job boards.

    Yields:
        The client.
    """
    async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as client:
        yield client


@dataclass(slots=True)
class Hooks:
    """The MCP server's outside world."""

    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = (
        async_session
    )
    http_client: Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]] = (
        _http_client
    )
    settings: Callable[[], Settings] = get_settings
    resolve_token: Callable[..., Awaitable[ResolvedToken | None]] = field(
        default=api_token_service.resolve
    )


hooks = Hooks()
