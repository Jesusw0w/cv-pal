import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from cv_pal.config import get_settings
from cv_pal.database import engine
from cv_pal.dependencies import CurrentUser, LLMClientDep
from cv_pal.error_handlers import register_error_handlers
from cv_pal.llm import get_llm_client
from cv_pal.routers import (
    analysis,
    applications,
    auth,
    cvs,
    jobs,
    linkedin,
    profile,
    reviews,
    users,
)

logger = logging.getLogger(__name__)


async def _log_llm_status() -> None:
    """Warn at start-up when the configured model cannot be used.

    Logged, not fatal: most of the product needs no model, so a missing one should not
    stop the app — but it should not first surface as a failed request either.
    """
    problem = await get_llm_client().check()
    if problem is None:
        logger.info("LLM available: %s", get_llm_client().model)
    else:
        logger.warning("LLM unavailable: %s", problem)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    The schema is owned by Alembic; nothing is created here. Run
    ``uv run alembic upgrade head`` before starting the app.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the running application.
    """
    # In the background, so a slow provider never delays start-up.
    probe = asyncio.create_task(_log_llm_status())
    yield
    probe.cancel()
    await engine.dispose()


app = FastAPI(title="CV Pal", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

register_error_handlers(app)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(cvs.router)
app.include_router(reviews.router)
app.include_router(analysis.router)
app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(linkedin.router)


@app.get("/health/live", tags=["health"])
async def health_live() -> dict[str, str]:
    """Report that the process is running.

    Returns:
        A status document.
    """
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> JSONResponse:
    """Report whether the application can serve traffic.

    Readiness depends on the database being reachable, so an orchestrator does not
    route traffic to an instance that cannot answer.

    Returns:
        A status document, with a 503 status when a dependency is unavailable.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # any failure means "not ready"
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check endpoint.

    Retained as an alias of the liveness probe for existing clients.

    Returns:
        A status document.
    """
    return {"status": "ok"}


@app.get("/health/llm", tags=["health"])
async def health_llm(_: CurrentUser, client: LLMClientDep) -> dict[str, str | None]:
    """Report whether the configured model can be used.

    Separate from readiness on purpose: the app serves most features without a model,
    so a missing one must not take it out of rotation. Signed-in only, since it names
    the model.

    Args:
        client: The configured language model client.

    Returns:
        The status, the model name, and what is wrong when it is unavailable.
    """
    problem = await client.check()
    return {
        "status": "ok" if problem is None else "unavailable",
        "model": client.model,
        "detail": problem,
    }
