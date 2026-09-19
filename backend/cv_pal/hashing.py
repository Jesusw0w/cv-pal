"""Password hashing.

New hashes are argon2id. bcrypt is retained for *verification only*, so accounts
created before the migration keep working; those hashes are upgraded transparently the
next time their owner logs in. See :func:`needs_rehash`.
"""

import logging

import argon2
import bcrypt

from cv_pal.constants import (
    DEFAULT_ARGON2_HASH_LENGTH,
    DEFAULT_ARGON2_MEMORY_COST_KIB,
    DEFAULT_ARGON2_PARALLELISM,
    DEFAULT_ARGON2_SALT_LENGTH,
    DEFAULT_ARGON2_TIME_COST,
    DEFAULT_BCRYPT_MAX_BYTES,
    DEFAULT_BCRYPT_PREFIXES,
)

logger = logging.getLogger(__name__)

_hasher = argon2.PasswordHasher(
    time_cost=DEFAULT_ARGON2_TIME_COST,
    memory_cost=DEFAULT_ARGON2_MEMORY_COST_KIB,
    parallelism=DEFAULT_ARGON2_PARALLELISM,
    hash_len=DEFAULT_ARGON2_HASH_LENGTH,
    salt_len=DEFAULT_ARGON2_SALT_LENGTH,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id.

    Args:
        password: The plaintext password.

    Returns:
        The encoded hash, including the algorithm and its parameters.
    """
    return _hasher.hash(password)


def _verify_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a legacy bcrypt hash.

    Args:
        plain_password: The plaintext password.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches.
    """
    encoded = plain_password.encode()
    if len(encoded) > DEFAULT_BCRYPT_MAX_BYTES:
        # bcrypt raises above its input limit. A password that long cannot have
        # produced this hash under the old policy, so it simply does not match.
        return False
    try:
        return bcrypt.checkpw(encoded, hashed_password.encode())
    except ValueError:
        logger.warning("Malformed bcrypt hash encountered during verification")
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a stored hash of either supported algorithm.

    Args:
        plain_password: The plaintext password to check.
        hashed_password: The stored hash, argon2id or legacy bcrypt.

    Returns:
        True if the password matches, False otherwise. A malformed or unrecognised
        hash is treated as a mismatch rather than an error, so a corrupt row cannot
        crash the login path.
    """
    if hashed_password.startswith(DEFAULT_BCRYPT_PREFIXES):
        return _verify_bcrypt(plain_password, hashed_password)

    try:
        return _hasher.verify(hashed_password, plain_password)
    except argon2.exceptions.VerificationError:
        return False
    except argon2.exceptions.InvalidHashError:
        logger.warning("Unrecognised password hash format encountered")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Report whether a stored hash should be replaced.

    True for every legacy bcrypt hash, and for argon2id hashes whose cost parameters
    no longer match the configured ones.

    Args:
        hashed_password: The stored hash.

    Returns:
        True if the hash should be recomputed after a successful verification.
    """
    if hashed_password.startswith(DEFAULT_BCRYPT_PREFIXES):
        return True
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except argon2.exceptions.InvalidHashError:
        return True
