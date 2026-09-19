from cv_pal.constants import (
    DEFAULT_ERROR_APPLICATION_DUPLICATE,
    DEFAULT_ERROR_APPLICATION_NOT_FOUND,
    DEFAULT_ERROR_CONNECTION_DUPLICATE,
    DEFAULT_ERROR_CONNECTION_NOT_FOUND,
    DEFAULT_ERROR_CV_NOT_FOUND,
    DEFAULT_ERROR_EMAIL_REGISTERED,
    DEFAULT_ERROR_INVALID_CREDENTIALS,
    DEFAULT_ERROR_INVALID_REFRESH_TOKEN,
    DEFAULT_ERROR_JOB_BOARD_UNAVAILABLE,
    DEFAULT_ERROR_LINKEDIN_EXPORT_EMPTY,
    DEFAULT_ERROR_LINKEDIN_NOT_FOUND,
    DEFAULT_ERROR_LINKEDIN_UNREADABLE,
    DEFAULT_ERROR_LLM_INVALID_RESPONSE,
    DEFAULT_ERROR_LLM_UNAVAILABLE,
    DEFAULT_ERROR_POSTING_DUPLICATE,
    DEFAULT_ERROR_POSTING_NOT_FOUND,
    DEFAULT_ERROR_PROFILE_TOO_EMPTY,
    DEFAULT_ERROR_RATE_LIMITED,
    DEFAULT_ERROR_REGISTRATION_CLOSED,
    DEFAULT_ERROR_SUGGESTION_NOT_FOUND,
    DEFAULT_ERROR_UNLISTABLE_SOURCE,
    DEFAULT_ERROR_UNSUPPORTED_FILE_TYPE,
    DEFAULT_ERROR_UNSUPPORTED_JOB_URL,
)


class AppError(Exception):
    """Base class for all domain errors raised by the service layer."""

    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None) -> None:
        """Initialise the error.

        Args:
            message: Optional override for the default message.
        """
        self.message = message or self.message
        super().__init__(self.message)


class NotFoundError(AppError):
    """A requested resource does not exist or is not visible to the caller."""


class ConflictError(AppError):
    """The request conflicts with the current state of a resource."""


class ValidationError(AppError):
    """The request is well formed but semantically invalid."""


class AuthenticationError(AppError):
    """The caller could not be authenticated."""

    message = DEFAULT_ERROR_INVALID_CREDENTIALS


class CVNotFoundError(NotFoundError):
    """The CV does not exist or belongs to another user."""

    message = DEFAULT_ERROR_CV_NOT_FOUND


class SuggestionNotFoundError(NotFoundError):
    """The suggestion does not exist or belongs to another user."""

    message = DEFAULT_ERROR_SUGGESTION_NOT_FOUND


class EmailAlreadyRegisteredError(ConflictError):
    """An account already exists for the given email address."""

    message = DEFAULT_ERROR_EMAIL_REGISTERED


class ForbiddenError(AppError):
    """The request is understood and authenticated, but not permitted."""


class RegistrationClosedError(ForbiddenError):
    """The instance is not accepting new accounts."""

    message = DEFAULT_ERROR_REGISTRATION_CLOSED


class FileTooLargeError(ValidationError):
    """The uploaded file exceeds the configured size limit."""


class EmptyProfileError(ValidationError):
    """There is not enough in the profile to write a grounded summary from.

    Refusing is the point. A summary generated from an empty profile could only be
    invented, and principle 2 says the system never writes experience the user did not
    enter — so the check is here, before the model is ever called.
    """

    def __init__(self) -> None:
        """Initialise the error with the message the user is shown."""
        super().__init__(DEFAULT_ERROR_PROFILE_TOO_EMPTY)


class UnsupportedFileTypeError(ValidationError):
    """The uploaded file type is not supported."""

    def __init__(self, suffix: str) -> None:
        """Initialise the error.

        Args:
            suffix: The rejected file suffix, including the leading dot.
        """
        super().__init__(DEFAULT_ERROR_UNSUPPORTED_FILE_TYPE.format(suffix=suffix))


class InvalidRefreshTokenError(AuthenticationError):
    """The refresh token is unknown, expired, revoked, or no longer usable."""

    message = DEFAULT_ERROR_INVALID_REFRESH_TOKEN


class RateLimitedError(AppError):
    """The caller has made too many attempts and must wait."""

    def __init__(self, retry_after: int) -> None:
        """Initialise the error.

        Args:
            retry_after: Seconds the caller should wait before retrying.
        """
        self.retry_after = retry_after
        super().__init__(DEFAULT_ERROR_RATE_LIMITED.format(retry_after=retry_after))


class LLMError(AppError):
    """The language model could not be reached or produced unusable output."""

    message = DEFAULT_ERROR_LLM_UNAVAILABLE


class LLMResponseError(LLMError):
    """The language model returned output that failed schema validation."""

    message = DEFAULT_ERROR_LLM_INVALID_RESPONSE


class JobBoardError(AppError):
    """A sanctioned job board could not be read.

    Deliberately one error for every failure mode — bad URL, timeout, 404, malformed
    JSON. The caller can do nothing different for each, and the user's next step is the
    same in all of them: paste the description instead.
    """

    message = DEFAULT_ERROR_JOB_BOARD_UNAVAILABLE


class PostingNotFoundError(NotFoundError):
    """No such job posting for this user."""

    message = DEFAULT_ERROR_POSTING_NOT_FOUND


class DuplicatePostingError(ConflictError):
    """The user already saved this posting."""

    message = DEFAULT_ERROR_POSTING_DUPLICATE


class ApplicationNotFoundError(NotFoundError):
    """No such application for this user."""

    message = DEFAULT_ERROR_APPLICATION_NOT_FOUND


class DuplicateApplicationError(ConflictError):
    """The user already recorded an application for this posting."""

    message = DEFAULT_ERROR_APPLICATION_DUPLICATE


class UnsupportedJobUrlError(ValidationError):
    """The URL is not a job board CV Pal reads.

    There is no general fetcher on purpose: fetching a user-supplied URL server-side is
    a request-forgery primitive, and scraping arbitrary careers pages breaks silently.
    See `integrations/job_boards.py`.
    """

    message = DEFAULT_ERROR_UNSUPPORTED_JOB_URL


class ConnectionNotFoundError(NotFoundError):
    """No such job board connection for this user."""

    message = DEFAULT_ERROR_CONNECTION_NOT_FOUND


class DuplicateConnectionError(ConflictError):
    """The user is already watching that board."""

    message = DEFAULT_ERROR_CONNECTION_DUPLICATE


class UnlistableSourceError(ValidationError):
    """The source has no board behind it to list."""

    message = DEFAULT_ERROR_UNLISTABLE_SOURCE


class LinkedInProfileNotFoundError(NotFoundError):
    """The user has not imported a LinkedIn profile yet."""

    message = DEFAULT_ERROR_LINKEDIN_NOT_FOUND


class LinkedInUnreadableError(ValidationError):
    """The uploaded document does not read as a LinkedIn profile.

    Refused rather than parsed on a best-effort basis: a review of the wrong document
    is worse than no review, because the user would act on it.
    """

    message = DEFAULT_ERROR_LINKEDIN_UNREADABLE


class LinkedInExportEmptyError(ValidationError):
    """The data-export archive carried none of the profile files."""

    message = DEFAULT_ERROR_LINKEDIN_EXPORT_EMPTY
