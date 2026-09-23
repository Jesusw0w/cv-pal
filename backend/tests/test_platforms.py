"""Job platforms: which ones still show an older profile, and which ones get replies."""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.helpers import register_and_login
from tests.test_applications import apply, save_posting


async def add(
    client: AsyncClient, headers: dict[str, str], **body: object
) -> dict[str, object]:
    """Track a platform and return it."""
    response = await client.post("/platforms", headers=headers, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def test_platforms_require_authentication(client: AsyncClient) -> None:
    """Where someone is looking for work is theirs to see."""
    assert (await client.get("/platforms")).status_code == 401


async def test_a_platform_with_no_update_date_is_unknown(client: AsyncClient) -> None:
    """Nothing to compare against is not the same as being behind."""
    headers = await register_and_login(client)

    platform = await add(client, headers, name="Hired Hands")

    assert platform["status"] == "unknown"


async def test_a_profile_change_after_the_update_makes_it_outdated(
    client: AsyncClient,
) -> None:
    """Adding a role counts as a profile change, not only editing the headline."""
    headers = await register_and_login(client)
    await client.get("/profile", headers=headers)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    platform = await add(
        client, headers, name="Hired Hands", profile_updated_on=yesterday
    )
    assert platform["status"] == "outdated"

    today = date.today().isoformat()
    updated = await client.patch(
        f"/platforms/{platform['id']}",
        headers=headers,
        json={"profile_updated_on": today},
    )
    assert updated.json()["status"] == "up_to_date"

    # Compared by day: a change made the same day the platform was updated is taken
    # to be on it, since people do both in one sitting.
    await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Initech",
            "title": "QA Tester",
            "start_date": "2010-06-01",
        },
    )
    listed = (await client.get("/platforms", headers=headers)).json()
    assert listed[0]["status"] == "up_to_date"


async def test_the_same_name_twice_is_refused(client: AsyncClient) -> None:
    """Names are how the user tells platforms apart in the dropdown."""
    headers = await register_and_login(client)
    await add(client, headers, name="Hired Hands")

    response = await client.post(
        "/platforms", headers=headers, json={"name": "  Hired   Hands "}
    )

    assert response.status_code == 400
    assert "already track" in response.text


async def test_an_update_date_in_the_future_is_refused(client: AsyncClient) -> None:
    """Saying a profile was updated tomorrow would mark it current until then."""
    headers = await register_and_login(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = await client.post(
        "/platforms",
        headers=headers,
        json={"name": "Hired Hands", "profile_updated_on": tomorrow},
    )

    assert response.status_code == 422


async def test_another_users_platform_does_not_exist(client: AsyncClient) -> None:
    """Neither to read, nor to cite on an application."""
    owner = await register_and_login(client)
    platform = await add(client, owner, name="Hired Hands")
    intruder = await register_and_login(client, email="intruder@example.com")

    patched = await client.patch(
        f"/platforms/{platform['id']}", headers=intruder, json={"notes": "mine"}
    )
    posting_id = await save_posting(client, intruder)
    cited = await client.post(
        "/applications",
        headers=intruder,
        json={"job_posting_id": posting_id, "platform_id": platform["id"]},
    )

    assert patched.status_code == 404
    assert cited.status_code == 404


async def test_reply_rates_are_reported_per_platform(client: AsyncClient) -> None:
    """The point of recording the platform: seeing which ones actually work."""
    headers = await register_and_login(client)
    board = await add(client, headers, name="Hired Hands")
    long_ago = (date.today() - timedelta(days=30)).isoformat()

    replied = await apply(
        client,
        headers,
        await save_posting(client, headers, title="Backend Engineer"),
        platform_id=board["id"],
        applied_at=long_ago,
    )
    await client.patch(
        f"/applications/{replied['id']}",
        headers=headers,
        json={"status": "interviewing"},
    )
    await apply(
        client,
        headers,
        await save_posting(client, headers, title="Platform Engineer"),
        platform_id=board["id"],
        applied_at=long_ago,
    )
    await apply(
        client,
        headers,
        await save_posting(client, headers, title="Data Engineer"),
        applied_at=long_ago,
    )

    rows = (await client.get("/applications/stats", headers=headers)).json()[
        "by_platform"
    ]

    assert [
        (r["name"], r["total"], r["reply_rate"], r["interviews"]) for r in rows
    ] == [
        ("Hired Hands", 2, 50, 1),
        ("Not recorded", 1, 0, 0),
    ]


async def test_deleting_a_platform_keeps_its_applications(client: AsyncClient) -> None:
    """The record of having applied outlives the platform it went through."""
    headers = await register_and_login(client)
    board = await add(client, headers, name="Hired Hands")
    application = await apply(
        client, headers, await save_posting(client, headers), platform_id=board["id"]
    )

    deleted = await client.delete(f"/platforms/{board['id']}", headers=headers)
    kept = (await client.get("/applications", headers=headers)).json()

    assert deleted.status_code == 204
    assert [(a["id"], a["platform_id"]) for a in kept] == [(application["id"], None)]


async def test_a_platform_records_where_setting_it_up_stands(
    client: AsyncClient,
) -> None:
    """Not started, later, active: part of the tracker, not only the update date."""
    headers = await register_and_login(client)

    later = await add(client, headers, name="Hired Hands", state="later")
    default = await add(client, headers, name="Job Hub")

    assert later["state"] == "later"
    assert default["state"] == "active"


async def test_an_application_without_a_saved_posting(client: AsyncClient) -> None:
    """Recorded from the role alone, with what was offered and what comes next."""
    headers = await register_and_login(client)

    response = await client.post(
        "/applications",
        headers=headers,
        json={
            "role": {"title": "Python Developer", "company": "Initech"},
            "salary": "€40-45k",
            "next_step": "Technical interview",
        },
    )
    both = await client.post(
        "/applications",
        headers=headers,
        json={"job_posting_id": 1, "role": {"title": "Python Developer"}},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["posting"]["title"] == "Python Developer"
    assert body["posting"]["description"] == ""
    assert (body["salary"], body["next_step"]) == ("€40-45k", "Technical interview")
    assert both.status_code == 422
