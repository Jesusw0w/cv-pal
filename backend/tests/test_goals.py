from httpx import AsyncClient

from tests.helpers import register_and_login


async def test_goals_are_created_empty_on_first_access(client: AsyncClient) -> None:
    """A new user has empty goals rather than a missing record."""
    headers = await register_and_login(client)

    response = await client.get("/profile/goals", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["target_roles"] == []
    assert body["work_regimes"] == []
    assert body["regime_non_negotiable"] is False
    assert body["min_salary"] is None


async def test_goals_require_authentication(client: AsyncClient) -> None:
    """Goals are not readable anonymously."""
    assert (await client.get("/profile/goals")).status_code == 401


async def test_goals_are_stored_and_returned(client: AsyncClient) -> None:
    """A full set of goals round-trips."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals",
        headers=headers,
        json={
            "target_roles": ["Backend Engineer", "Platform Engineer"],
            "work_regimes": ["remote", "hybrid"],
            "regime_non_negotiable": True,
            "min_salary": 65000,
            "salary_currency": "eur",
            "salary_non_negotiable": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target_roles"] == ["Backend Engineer", "Platform Engineer"]
    # Order is a preference, best first, so it must survive the round trip.
    assert body["work_regimes"] == ["remote", "hybrid"]
    assert body["regime_non_negotiable"] is True
    assert body["salary_currency"] == "EUR"

    assert (await client.get("/profile/goals", headers=headers)).json() == body


async def test_put_replaces_rather_than_merges(client: AsyncClient) -> None:
    """An omitted preference is cleared, not left alone.

    This is the whole reason the endpoint is a PUT: with a merge there would be no way
    to remove a salary floor without a separate delete.
    """
    headers = await register_and_login(client)

    await client.put(
        "/profile/goals",
        headers=headers,
        json={
            "target_roles": ["Backend Engineer"],
            "min_salary": 65000,
            "salary_currency": "EUR",
        },
    )
    response = await client.put(
        "/profile/goals", headers=headers, json={"work_regimes": ["remote"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target_roles"] == []
    assert body["min_salary"] is None
    assert body["salary_currency"] is None


async def test_role_titles_are_trimmed_and_deduplicated(client: AsyncClient) -> None:
    """A form will send blanks and repeats; they are not the user's intent."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals",
        headers=headers,
        json={
            "target_roles": [
                "  Backend   Engineer ",
                "",
                "Backend Engineer",
                "   ",
                "Platform Engineer",
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["target_roles"] == ["Backend Engineer", "Platform Engineer"]


async def test_non_negotiable_regime_with_no_regimes_is_rejected(
    client: AsyncClient,
) -> None:
    """A non-negotiable with nothing behind it filters out every posting."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals",
        headers=headers,
        json={"work_regimes": [], "regime_non_negotiable": True},
    )

    assert response.status_code == 422
    assert "non-negotiable" in response.text


async def test_non_negotiable_salary_with_no_floor_is_rejected(
    client: AsyncClient,
) -> None:
    """Same trap on the salary side."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals", headers=headers, json={"salary_non_negotiable": True}
    )

    assert response.status_code == 422


async def test_salary_without_currency_is_rejected(client: AsyncClient) -> None:
    """A bare number cannot be compared to a posting's band."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals", headers=headers, json={"min_salary": 65000}
    )

    assert response.status_code == 422
    assert "currency" in response.text


async def test_duplicate_work_regimes_are_rejected(client: AsyncClient) -> None:
    """An ordered preference cannot rank the same option twice."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals", headers=headers, json={"work_regimes": ["remote", "remote"]}
    )

    assert response.status_code == 422


async def test_unknown_work_regime_is_rejected(client: AsyncClient) -> None:
    """The enum is the contract; free text here would break matching silently."""
    headers = await register_and_login(client)

    response = await client.put(
        "/profile/goals", headers=headers, json={"work_regimes": ["hammock"]}
    )

    assert response.status_code == 422


async def test_goals_are_per_user(client: AsyncClient) -> None:
    """One user's goals are invisible to another."""
    first = await register_and_login(client, email="one@example.com")
    second = await register_and_login(client, email="two@example.com")

    await client.put(
        "/profile/goals", headers=first, json={"target_roles": ["Backend Engineer"]}
    )

    assert (await client.get("/profile/goals", headers=second)).json()[
        "target_roles"
    ] == []
