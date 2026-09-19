import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cv_pal.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    FileTooLargeError,
    ForbiddenError,
    JobBoardError,
    LLMError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Domain error -> HTTP status. Ordered most specific first: the first class the
# exception is an instance of wins.
_STATUS_BY_ERROR: tuple[tuple[type[AppError], int], ...] = (
    (FileTooLargeError, status.HTTP_413_CONTENT_TOO_LARGE),
    (RateLimitedError, status.HTTP_429_TOO_MANY_REQUESTS),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ForbiddenError, status.HTTP_403_FORBIDDEN),
    (ConflictError, status.HTTP_400_BAD_REQUEST),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (ValidationError, status.HTTP_400_BAD_REQUEST),
    (LLMError, status.HTTP_502_BAD_GATEWAY),
    (JobBoardError, status.HTTP_502_BAD_GATEWAY),
)


def status_for(error: AppError) -> int:
    """Map a domain error to an HTTP status code.

    Args:
        error: The domain error raised by a service.

    Returns:
        The HTTP status code to respond with.
    """
    for error_type, status_code in _STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status_code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    """Translate a domain error into a JSON error response.

    Args:
        request: The incoming request.
        exc: The domain error raised while handling it.

    Returns:
        A JSON response carrying the error message.
    """
    assert isinstance(exc, AppError)  # noqa: S101  # registered for AppError only
    status_code = status_for(exc)
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("Unhandled domain error on %s: %s", request.url.path, exc)

    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
        headers=headers or None,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Report a request-validation failure without echoing what was submitted.

    FastAPI's default handler returns each error with an ``input`` key holding the value
    that failed. On ``POST /auth/register`` that value is the request body — **including
    the plaintext password** — so every rejected registration put the user's password
    into a response body, where it reaches browser devtools, any reverse proxy that logs
    bodies, and any error-reporting client the deployer puts in front of the app.

    Only the machine-readable shape a client actually needs is kept: what failed, where,
    and why. ``ctx`` goes with ``input`` because a Pydantic context can carry the value
    too.

    Args:
        request: The incoming request.
        exc: The validation error raised while parsing it.

    Returns:
        A 422 carrying the error type, location and message, and nothing else.
    """
    assert isinstance(exc, RequestValidationError)  # noqa: S101  # registered for it
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": [
                {"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
                for error in exc.errors()
            ]
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register domain error handlers on the application.

    Keeping the mapping here is what lets the service layer stay framework-free: it
    raises domain errors, and only the edge knows about HTTP.

    Args:
        app: The FastAPI application.
    """
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
