from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.models import CV, CareerProfile, RefreshToken, User
from tests.helpers import (
    DEFAULT_TEST_EMAIL,
    DEFAULT_TEST_PASSWORD,
    register_and_login,
    upload_cv,
)

PASSWORD = DEFAULT_TEST_PASSWORD
NEW_PASSWORD = "tangential-walrus-4-anvil"  # noqa: S105  # test fixture credential


async def test_name_can_be_set_after_registration(client: AsyncClient) -> None:
    """The name heads every generated CV, and registration leaves it optional."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/users/me", headers=headers, json={"full_name": "  Ana Silva  "}
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ana Silva"

    stored = await client.get("/users/me", headers=headers)
    assert stored.json()["full_name"] == "Ana Silva"


async def test_blank_name_clears_rather_than_heading_a_cv_with_spaces(
    client: AsyncClient,
) -> None:
    """Whitespace is not a name; it would render as an empty heading."""
    headers = await register_and_login(client)
    await client.patch("/users/me", headers=headers, json={"full_name": "Ana Silva"})

    response = await client.patch(
        "/users/me", headers=headers, json={"full_name": "   "}
    )

    assert response.status_code == 200
    assert response.json()["full_name"] is None


async def test_password_change_requires_the_current_one(client: AsyncClient) -> None:
    """A stolen access token must not be enough to take the account permanently."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401


async def test_password_change_ends_every_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A password change that leaves the thief's refresh token working is theatre."""
    headers = await register_and_login(client)
    live = (
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.revoked_at.is_(None))
    )
    before = await db_session.scalar(live)
    assert before and before > 0

    response = await client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    # Revoked, not deleted: the row is what lets a replayed token be recognised later.
    assert await db_session.scalar(live) == 0

    # The new one works and the old one does not, which is the whole point.
    refused = await client.post(
        "/auth/login", data={"username": DEFAULT_TEST_EMAIL, "password": PASSWORD}
    )
    assert refused.status_code == 401
    accepted = await client.post(
        "/auth/login", data={"username": DEFAULT_TEST_EMAIL, "password": NEW_PASSWORD}
    )
    assert accepted.status_code == 200


async def test_password_change_voids_live_access_tokens(client: AsyncClient) -> None:
    """The access token used for the change stops working at once, not in 30 minutes."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    assert (await client.get("/users/me", headers=headers)).status_code == 401


async def test_password_change_holds_the_new_one_to_the_policy(
    client: AsyncClient,
) -> None:
    """The registration policy is not something a later change can step around."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "short"},
    )

    assert response.status_code == 422


async def test_password_change_refuses_the_same_password(client: AsyncClient) -> None:
    """Changing it to itself reports success while changing nothing."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )

    assert response.status_code == 422


async def test_export_covers_what_the_delete_destroys(client: AsyncClient) -> None:
    """An export that omits what deletion takes is worse than none — it reassures.

    Both walk the same loaded account, so this is a real coupling: a relationship added
    to one reaches the other.
    """
    headers = await register_and_login(client)
    await upload_cv(client, headers)
    await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Acme",
            "title": "Engineer",
            "start_date": "2021-01-01",
            "end_date": None,
        },
    )
    await client.patch("/profile", headers=headers, json={"headline": "Engineer"})

    response = await client.get("/users/me/export", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == DEFAULT_TEST_EMAIL
    assert body["profile"]["headline"] == "Engineer"
    assert [role["organisation"] for role in body["profile"]["experiences"]] == ["Acme"]
    assert len(body["documents"]) == 1
    for section in ("goals", "job_postings", "cover_letters", "linkedin_profile"):
        assert section in body


async def test_export_is_only_ever_the_callers_own_account(client: AsyncClient) -> None:
    """A URL returning a whole account is the one that must never cross accounts."""
    owner = await register_and_login(client)
    await client.patch("/profile", headers=owner, json={"headline": "Owner headline"})

    intruder = await register_and_login(client, email="intruder@example.com")
    response = await client.get("/users/me/export", headers=intruder)

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "intruder@example.com"
    assert response.json()["profile"] != {"headline": "Owner headline"}


async def test_delete_account_requires_the_password(client: AsyncClient) -> None:
    """The one irreversible action in the product asks who is asking."""
    headers = await register_and_login(client)

    response = await client.request(
        "DELETE", "/users/me", headers=headers, json={"password": "wrong"}
    )

    assert response.status_code == 401


async def test_delete_account_removes_everything_including_the_files(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Principle 4: an account that is only marked deleted is one the operator keeps.

    The file check is the part a cascade cannot do for us — uploads live outside the
    database, so a delete that only clears rows leaves someone's CV on the disk.
    """
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Acme",
            "title": "Engineer",
            "start_date": "2021-01-01",
            "end_date": None,
        },
    )

    stored = await db_session.scalar(select(CV.file_path).where(CV.id == cv_id))
    assert stored is not None
    assert Path(stored).exists()

    response = await client.request(
        "DELETE", "/users/me", headers=headers, json={"password": PASSWORD}
    )

    assert response.status_code == 204
    assert not Path(stored).exists()
    for model in (User, CV, CareerProfile, RefreshToken):
        remaining = await db_session.scalar(select(func.count()).select_from(model))
        assert remaining == 0, f"{model.__name__} rows survived the delete"


async def test_deleted_account_cannot_sign_back_in(client: AsyncClient) -> None:
    """A deleted account must be indistinguishable from one that never existed."""
    headers = await register_and_login(client)
    await client.request(
        "DELETE", "/users/me", headers=headers, json={"password": PASSWORD}
    )

    response = await client.post(
        "/auth/login", data={"username": DEFAULT_TEST_EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 401
