import bcrypt

from cv_pal.constants import DEFAULT_ARGON2_MEMORY_COST_KIB
from cv_pal.hashing import hash_password, needs_rehash, verify_password

LEGACY_PASSWORD = "legacy-bcrypt-9-pass"  # noqa: S105  # test fixture credential


def legacy_bcrypt_hash(password: str) -> str:
    """Produce a hash in the format the project used before argon2id.

    Args:
        password: The plaintext password.

    Returns:
        A bcrypt hash.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def test_new_hashes_are_argon2id() -> None:
    """Newly created hashes use argon2id, not bcrypt."""
    hashed = hash_password("orbital-lemur-7-quilt")

    assert hashed.startswith("$argon2id$")


def test_argon2_round_trip() -> None:
    """A password verifies against its own argon2id hash."""
    hashed = hash_password("orbital-lemur-7-quilt")

    assert verify_password("orbital-lemur-7-quilt", hashed)
    assert not verify_password("not-the-password-1", hashed)


def test_argon2_uses_the_configured_cost() -> None:
    """The encoded hash carries the configured memory cost."""
    hashed = hash_password("orbital-lemur-7-quilt")

    assert f"m={DEFAULT_ARGON2_MEMORY_COST_KIB}" in hashed


def test_legacy_bcrypt_hashes_still_verify() -> None:
    """Accounts created before the migration keep working."""
    hashed = legacy_bcrypt_hash(LEGACY_PASSWORD)

    assert verify_password(LEGACY_PASSWORD, hashed)
    assert not verify_password("wrong-password-99", hashed)


def test_legacy_hashes_are_flagged_for_rehash() -> None:
    """A bcrypt hash is always due for replacement."""
    assert needs_rehash(legacy_bcrypt_hash(LEGACY_PASSWORD))


def test_current_argon2_hashes_are_not_flagged() -> None:
    """A hash at the configured parameters does not need replacing."""
    assert not needs_rehash(hash_password("orbital-lemur-7-quilt"))


def test_passwords_longer_than_bcrypts_limit_are_supported() -> None:
    """argon2id removes the 72-byte ceiling bcrypt imposed."""
    password = "a1" + "b" * 200
    assert len(password.encode()) > 72

    hashed = hash_password(password)

    assert verify_password(password, hashed)


def test_bcrypt_verification_rejects_overlong_input_without_raising() -> None:
    """A too-long password against a legacy hash is a mismatch, not a crash."""
    hashed = legacy_bcrypt_hash(LEGACY_PASSWORD)

    assert not verify_password("x" * 100, hashed)


def test_malformed_hash_is_a_mismatch_not_an_error() -> None:
    """A corrupt stored hash cannot crash the login path."""
    assert not verify_password("orbital-lemur-7-quilt", "not-a-real-hash")
    assert needs_rehash("not-a-real-hash")
