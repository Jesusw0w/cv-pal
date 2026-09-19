import re
import unicodedata

from cv_pal.common_passwords import COMMON_PASSWORDS
from cv_pal.constants import (
    DEFAULT_APP_NAME_TOKENS,
    DEFAULT_ERROR_PASSWORD_COMMON,
    DEFAULT_ERROR_PASSWORD_CONTEXTUAL,
    DEFAULT_ERROR_PASSWORD_TOO_LONG,
    DEFAULT_ERROR_PASSWORD_TOO_SHORT,
    DEFAULT_MAX_PASSWORD_BYTES,
    DEFAULT_MIN_CONTEXT_TOKEN_LENGTH,
    DEFAULT_MIN_PASSWORD_LENGTH,
)

_TRAILING_PADDING = re.compile(r"[\W\d_]+$", flags=re.UNICODE)
_NON_ALNUM = re.compile(r"[\W_]+", flags=re.UNICODE)


def _normalise(password: str) -> str:
    """Reduce a password to a comparable form for blocklist screening.

    Args:
        password: The raw password.

    Returns:
        A lowercased, NFKC-normalised form.
    """
    return unicodedata.normalize("NFKC", password).casefold()


def _blocklist_variants(password: str) -> set[str]:
    """Build the forms of a password to test against the common-password list.

    ``Password123!`` must be caught as readily as ``password`` — appending digits and a
    symbol is the single most common way of satisfying a composition rule without
    adding meaningful entropy.

    Args:
        password: The raw password.

    Returns:
        The normalised forms to screen.
    """
    normalised = _normalise(password)
    return {
        normalised,
        _TRAILING_PADDING.sub("", normalised),
        _NON_ALNUM.sub("", normalised),
    }


def _context_tokens(email: str | None) -> set[str]:
    """Derive values a password must not be built from.

    Args:
        email: The account's email address, if known.

    Returns:
        Lowercased tokens drawn from the email and the application name.
    """
    tokens = set(DEFAULT_APP_NAME_TOKENS)
    if email:
        local_part, _, domain = email.partition("@")
        tokens.add(local_part.casefold())
        tokens.update(
            part.casefold()
            for part in _NON_ALNUM.split(local_part)
            if len(part) >= DEFAULT_MIN_CONTEXT_TOKEN_LENGTH
        )
        domain_name, _, _ = domain.partition(".")
        if domain_name:
            tokens.add(domain_name.casefold())
    return {token for token in tokens if len(token) >= DEFAULT_MIN_CONTEXT_TOKEN_LENGTH}


def validate_password(password: str, *, email: str | None = None) -> str:
    """Validate a password against the project's password policy.

    The policy follows NIST SP 800-63B: length and screening do the work, not
    composition theatre. See the *Password policy* section of ``docs/PLANNING.md``.

    Args:
        password: The raw password.
        email: The account's email address, used to reject context-specific values.

    Returns:
        The unchanged password, so this can be used directly by a validator.

    Raises:
        ValueError: If the password is too short, exceeds bcrypt's 72-byte input limit,
            appears in the common-password list, or is derived from the user's own email
            or the application name.
    """
    if len(password) < DEFAULT_MIN_PASSWORD_LENGTH:
        raise ValueError(
            DEFAULT_ERROR_PASSWORD_TOO_SHORT.format(minimum=DEFAULT_MIN_PASSWORD_LENGTH)
        )

    # bcrypt raises above 72 bytes rather than truncating, and UTF-8 means a
    # short-looking password can exceed it. Unmeasured, that is a 500 not a 422.
    if len(password.encode("utf-8")) > DEFAULT_MAX_PASSWORD_BYTES:
        raise ValueError(
            DEFAULT_ERROR_PASSWORD_TOO_LONG.format(maximum=DEFAULT_MAX_PASSWORD_BYTES)
        )

    if _blocklist_variants(password) & COMMON_PASSWORDS:
        raise ValueError(DEFAULT_ERROR_PASSWORD_COMMON)

    normalised = _normalise(password)
    if any(token in normalised for token in _context_tokens(email)):
        raise ValueError(DEFAULT_ERROR_PASSWORD_CONTEXTUAL)

    return password
