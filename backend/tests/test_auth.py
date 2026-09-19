import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.config import get_settings
from cv_pal.constants import (
    DEFAULT_ERROR_EMAIL_REGISTERED,
    DEFAULT_ERROR_INVALID_CREDENTIALS,
    DEFAULT_LOCKOUT_THRESHOLD,
)
from cv_pal.main import app
from cv_pal.models import User
from cv_pal.rate_limit import InMemoryRateLimiter, get_rate_limiter
from tests.helpers import DEFAULT_TEST_EMAIL, DEFAULT_TEST_PASSWORD, register_and_login


async def test_register_user(client: AsyncClient) -> None:
    """A new user can register."""
    response = await client.post(
        "/auth/register",
        json={
            "email": DEFAULT_TEST_EMAIL,
            "password": DEFAULT_TEST_PASSWORD,
            "full_name": "Test User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == DEFAULT_TEST_EMAIL
    assert data["full_name"] == "Test User"
    assert "id" in data


async def test_register_never_returns_password(client: AsyncClient) -> None:
    """The registration response exposes no credential material."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Registering an existing email is rejected."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": "different-9-passphrase"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == DEFAULT_ERROR_EMAIL_REGISTERED


async def test_a_rejected_password_is_not_echoed_back(client: AsyncClient) -> None:
    """A 422 must not carry the submitted password.

    FastAPI's default validation handler returns the offending value under `input`,
    which on this endpoint is the whole request body. That put the plaintext password in
    a response body on every rejected registration.
    """
    secret = "correct-horse-battery-staple"  # noqa: S105  # a test value, not a secret
    response = await client.post(
        "/auth/register",
        json={"email": "nobody@example.invalid", "password": secret[:4]},
    )

    assert response.status_code == 422
    assert secret[:4] not in response.text
    assert "input" not in response.text


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    """A password below the minimum length fails validation."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": "sh0rt"},
    )

    assert response.status_code == 422


async def test_register_rejects_absurdly_long_password(client: AsyncClient) -> None:
    """The denial-of-service ceiling is a validation error, not a crash."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": "a1" + "b" * 5000},
    )

    assert response.status_code == 422


async def test_register_rejects_common_password(client: AsyncClient) -> None:
    """A well-known password is screened out."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": "Password123!"},
    )

    assert response.status_code == 422


async def test_register_rejects_password_derived_from_email(
    client: AsyncClient,
) -> None:
    """A password built from the user's own email is rejected."""
    response = await client.post(
        "/auth/register",
        json={"email": "marchel@example.com", "password": "marchel-2024-x"},
    )

    assert response.status_code == 422


async def test_login(client: AsyncClient) -> None:
    """A registered user can log in and receive a token."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    response = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client: AsyncClient) -> None:
    """Logging in with the wrong password is rejected."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    response = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == DEFAULT_ERROR_INVALID_CREDENTIALS


async def test_login_unknown_email(client: AsyncClient) -> None:
    """An unknown email is rejected with the same message as a wrong password."""
    response = await client.post(
        "/auth/login",
        data={"username": "nobody@example.com", "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == DEFAULT_ERROR_INVALID_CREDENTIALS


async def test_get_current_user(client: AsyncClient) -> None:
    """The authenticated user can read their own profile."""
    headers = await register_and_login(client)

    response = await client.get("/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == DEFAULT_TEST_EMAIL


async def test_get_current_user_no_token(client: AsyncClient) -> None:
    """Reading the profile without a token is rejected."""
    response = await client.get("/users/me")

    assert response.status_code == 401


async def test_login_upgrades_a_legacy_bcrypt_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A pre-argon2 account is migrated transparently on next login."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    # Rewrite the stored hash to the format the project used before argon2id.
    user = (
        await db_session.execute(select(User).where(User.email == DEFAULT_TEST_EMAIL))
    ).scalar_one()
    user.hashed_password = bcrypt.hashpw(
        DEFAULT_TEST_PASSWORD.encode(), bcrypt.gensalt()
    ).decode()
    await db_session.commit()

    response = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 200
    await db_session.refresh(user)
    assert user.hashed_password.startswith("$argon2id$")


async def test_login_rate_limited_by_client(client: AsyncClient) -> None:
    """Too many login attempts from one client are throttled with a Retry-After."""
    # A one-request quota, so the second call is throttled without paying for ten
    # argon2 hashes first. Replaces the override the client fixture installed.
    strict = InMemoryRateLimiter(requests=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: strict

    first = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    second = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    assert first.status_code == 401
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


async def test_register_is_rate_limited_too(client: AsyncClient) -> None:
    """Registration is throttled per client as well as login."""
    strict = InMemoryRateLimiter(requests=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: strict
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    response = await client.post(
        "/auth/register",
        json={"email": "second@example.com", "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 429


async def test_repeated_failures_lock_the_account(client: AsyncClient) -> None:
    """Consecutive wrong passwords put the account into backoff."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    statuses = []
    for _ in range(DEFAULT_LOCKOUT_THRESHOLD + 2):
        response = await client.post(
            "/auth/login",
            data={"username": DEFAULT_TEST_EMAIL, "password": "wrong-password-1"},
        )
        statuses.append(response.status_code)

    assert statuses[0] == 401
    assert statuses[-1] == 429


async def test_lockout_applies_to_unknown_emails_too(client: AsyncClient) -> None:
    """Backoff cannot be used to discover which addresses are registered."""
    statuses = []
    for _ in range(DEFAULT_LOCKOUT_THRESHOLD + 2):
        response = await client.post(
            "/auth/login",
            data={"username": "nobody@example.com", "password": "wrong-password-1"},
        )
        statuses.append(response.status_code)

    assert statuses[-1] == 429


async def test_successful_login_clears_the_failure_count(client: AsyncClient) -> None:
    """A correct password resets the backoff so the next mistake is not punished."""
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    for _ in range(DEFAULT_LOCKOUT_THRESHOLD):
        await client.post(
            "/auth/login",
            data={"username": DEFAULT_TEST_EMAIL, "password": "wrong-password-1"},
        )

    good = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    after = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": "wrong-password-1"},
    )

    assert good.status_code == 200
    assert after.status_code == 401


async def test_register_accepts_a_password_longer_than_bcrypts_limit(
    client: AsyncClient,
) -> None:
    """argon2id removes the old 72-byte ceiling."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": "a1" + "b" * 100},
    )

    assert response.status_code == 201


async def test_get_current_user_invalid_token(client: AsyncClient) -> None:
    """A malformed token is rejected."""
    response = await client.get(
        "/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


async def test_registration_can_be_closed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exposed instance must be able to stop accepting new accounts.

    Exercised through the environment rather than by patching, because the env-var path
    is the one a self-hoster actually uses.
    """
    monkeypatch.setenv("CV_PAL_ALLOW_REGISTRATION", "false")
    get_settings.cache_clear()

    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 403
