from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.auth import hash_refresh_token
from cv_pal.models import RefreshToken, User
from tests.helpers import DEFAULT_TEST_EMAIL, DEFAULT_TEST_PASSWORD


async def login(client: AsyncClient) -> tuple[str, str]:
    """Register (idempotently) and log in, returning both tokens.

    Args:
        client: The test HTTP client.

    Returns:
        A tuple of ``(access_token, refresh_token)``.
    """
    await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    response = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    body = response.json()
    return body["access_token"], body["refresh_token"]


async def test_login_returns_a_refresh_token(client: AsyncClient) -> None:
    """A successful login issues both tokens."""
    response = await client.post(
        "/auth/register",
        json={"email": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )
    assert response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
    )

    body = login_response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"  # noqa: S105  # scheme name, not a secret


async def test_only_the_hash_is_stored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The plaintext refresh token never reaches the database."""
    _, refresh_token = await login(client)

    stored = (await db_session.execute(select(RefreshToken))).scalars().all()

    assert len(stored) == 1
    assert stored[0].token_hash == hash_refresh_token(refresh_token)
    assert refresh_token not in stored[0].token_hash


async def test_refresh_returns_a_working_access_token(client: AsyncClient) -> None:
    """The access token from a refresh authenticates requests."""
    _, refresh_token = await login(client)

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    me = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me.status_code == 200


async def test_refresh_rotates_the_token(client: AsyncClient) -> None:
    """Refreshing issues a different refresh token."""
    _, refresh_token = await login(client)

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.json()["refresh_token"] != refresh_token


async def test_refresh_token_is_single_use(client: AsyncClient) -> None:
    """The presented token is revoked once exchanged."""
    _, refresh_token = await login(client)
    await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    second = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert second.status_code == 401


async def test_reuse_revokes_every_session(client: AsyncClient) -> None:
    """Replaying a spent token invalidates the whole chain, not just itself.

    Two parties cannot both legitimately hold a one-time token, so a replay is treated
    as evidence of theft and every session for that user is ended.
    """
    _, first_token = await login(client)
    rotated = (
        await client.post("/auth/refresh", json={"refresh_token": first_token})
    ).json()["refresh_token"]

    # The attacker replays the spent token.
    replay = await client.post("/auth/refresh", json={"refresh_token": first_token})
    # The legitimate holder's current token must now be dead too.
    legitimate = await client.post("/auth/refresh", json={"refresh_token": rotated})

    assert replay.status_code == 401
    assert legitimate.status_code == 401


async def test_expired_refresh_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A token past its expiry cannot be exchanged."""
    _, refresh_token = await login(client)
    stored = (await db_session.execute(select(RefreshToken))).scalar_one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401


async def test_unknown_refresh_token_is_rejected(client: AsyncClient) -> None:
    """A fabricated token is rejected."""
    response = await client.post(
        "/auth/refresh", json={"refresh_token": "not-a-real-token"}
    )

    assert response.status_code == 401


async def test_logout_revokes_the_session(client: AsyncClient) -> None:
    """After logout the refresh token no longer works."""
    _, refresh_token = await login(client)

    logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    after = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert logout.status_code == 204
    assert after.status_code == 401


async def test_logout_is_idempotent(client: AsyncClient) -> None:
    """Logging out twice, or with an unknown token, still succeeds."""
    _, refresh_token = await login(client)
    await client.post("/auth/logout", json={"refresh_token": refresh_token})

    again = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    unknown = await client.post("/auth/logout", json={"refresh_token": "nonsense"})

    assert again.status_code == 204
    assert unknown.status_code == 204


async def test_logout_all_ends_every_session(client: AsyncClient) -> None:
    """Logging out everywhere invalidates sessions issued separately."""
    access, first = await login(client)
    second = (
        await client.post(
            "/auth/login",
            data={"username": DEFAULT_TEST_EMAIL, "password": DEFAULT_TEST_PASSWORD},
        )
    ).json()["refresh_token"]

    response = await client.post(
        "/auth/logout-all", headers={"Authorization": f"Bearer {access}"}
    )

    assert response.status_code == 204
    for token in (first, second):
        assert (
            await client.post("/auth/refresh", json={"refresh_token": token})
        ).status_code == 401
    # Access tokens too, not only refresh tokens.
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401


async def test_logout_all_requires_authentication(client: AsyncClient) -> None:
    """Ending every session is not something an anonymous caller may do."""
    response = await client.post("/auth/logout-all")

    assert response.status_code == 401


async def test_refresh_rejected_for_deactivated_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deactivating an account stops its sessions from being renewed."""
    _, refresh_token = await login(client)
    user = (
        await db_session.execute(select(User).where(User.email == DEFAULT_TEST_EMAIL))
    ).scalar_one()
    user.is_active = False
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401
