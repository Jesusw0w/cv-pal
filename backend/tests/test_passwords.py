import re

import pytest

from cv_pal.constants import (
    DEFAULT_ERROR_PASSWORD_COMMON,
    DEFAULT_ERROR_PASSWORD_CONTEXTUAL,
    DEFAULT_MAX_PASSWORD_BYTES,
    DEFAULT_MIN_PASSWORD_LENGTH,
)
from cv_pal.hashing import hash_password, verify_password
from cv_pal.passwords import validate_password


def test_accepts_a_reasonable_passphrase() -> None:
    """A long, unpredictable passphrase passes."""
    assert validate_password("orbital-lemur-7-quilt") == "orbital-lemur-7-quilt"


@pytest.mark.parametrize("password", ["sh0rt", "a1b2c3d4e5"])
def test_rejects_short_passwords(password: str) -> None:
    """Anything below the minimum length is rejected."""
    assert len(password) < DEFAULT_MIN_PASSWORD_LENGTH

    with pytest.raises(ValueError, match="at least"):
        validate_password(password)


def test_rejects_passwords_over_the_bcrypt_byte_limit() -> None:
    """A password longer than bcrypt accepts fails validation rather than hashing."""
    password = "a1" + "b" * DEFAULT_MAX_PASSWORD_BYTES

    with pytest.raises(ValueError, match="bytes"):
        validate_password(password)


def test_byte_limit_counts_utf8_bytes_not_characters() -> None:
    """A password within the character count can still exceed the byte ceiling."""
    # Three bytes per character under UTF-8, so the byte count is triple the length.
    password = "字" * 350 + "1"
    assert len(password) < DEFAULT_MAX_PASSWORD_BYTES
    assert len(password.encode("utf-8")) > DEFAULT_MAX_PASSWORD_BYTES

    with pytest.raises(ValueError, match="bytes"):
        validate_password(password)


def test_accepts_a_password_exactly_at_the_byte_limit() -> None:
    """The boundary itself is allowed."""
    password = "a1" + "b" * (DEFAULT_MAX_PASSWORD_BYTES - 2)
    assert len(password.encode("utf-8")) == DEFAULT_MAX_PASSWORD_BYTES

    assert validate_password(password) == password


@pytest.mark.parametrize(
    "password",
    [
        "correcthorsebatterystaple",
        "qwertyuiop123",
        "administrator",
    ],
)
def test_rejects_common_passwords(password: str) -> None:
    """Well-known passwords are screened out."""
    with pytest.raises(ValueError, match=re.escape(DEFAULT_ERROR_PASSWORD_COMMON)):
        validate_password(password)


@pytest.mark.parametrize("password", ["password1234", "Password123!", "qwerty123456"])
def test_rejects_common_passwords_with_padding(password: str) -> None:
    """Appending digits and symbols does not defeat the blocklist."""
    with pytest.raises(ValueError, match=re.escape(DEFAULT_ERROR_PASSWORD_COMMON)):
        validate_password(password)


def test_rejects_password_derived_from_email() -> None:
    """A password built from the user's own email is rejected."""
    with pytest.raises(ValueError, match=re.escape(DEFAULT_ERROR_PASSWORD_CONTEXTUAL)):
        validate_password("inesmarques1990!!", email="inesmarques@example.com")


def test_rejects_password_containing_the_app_name() -> None:
    """A password built from the application name is rejected."""
    with pytest.raises(ValueError, match=re.escape(DEFAULT_ERROR_PASSWORD_CONTEXTUAL)):
        validate_password("my-cvpal-login-9")


def test_accepts_a_passphrase_with_no_digit() -> None:
    """No composition rule: SP 800-63B tells verifiers not to impose one.

    This exact passphrase was rejected by the digit rule that used to live here, while
    `Password1!` satisfied it — the inversion that made the rule worth deleting.
    """
    assert validate_password("orbital-lemur-quilt") == "orbital-lemur-quilt"


def test_email_is_optional() -> None:
    """Validation works when no email context is available."""
    assert validate_password("orbital-lemur-7-quilt", email=None)


def test_policy_limit_agrees_with_the_hasher() -> None:
    """Anything the policy accepts must be hashable.

    Guards the two limits against drifting apart: bcrypt raises above 72 bytes, so a
    policy that allowed more would turn registration into a 500.
    """
    password = "a1" + "b" * (DEFAULT_MAX_PASSWORD_BYTES - 2)
    validate_password(password)

    hashed = hash_password(password)

    assert verify_password(password, hashed)
