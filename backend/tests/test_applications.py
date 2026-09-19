"""Applications: the step that turns a CV tool into a job search.

The interesting tests here are the two about time. Reply rate and "needs chasing" are
both statements about intervals, and both are easy to get subtly wrong in ways that
show the user a confident, false number.
"""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.helpers import register_and_login, upload_cv

POSTING = (
    "We are hiring a Senior Backend Engineer. Requirements: strong Python experience, "
    "PostgreSQL and Docker. This role is fully remote."
)


async def save_posting(
    client: AsyncClient, headers: dict[str, str], title: str = "Senior Backend Engineer"
) -> int:
    """Save a pasted posting and return its id."""
    response = await client.post(
        "/jobs/paste",
        headers=headers,
        json={"title": title, "company": "Acme", "description": POSTING},
    )
    posting_id: int = response.json()["id"]
    return posting_id


async def apply(
    client: AsyncClient, headers: dict[str, str], posting_id: int, **overrides: object
) -> dict[str, object]:
    """Record an application and return it."""
    body: dict[str, object] = {"job_posting_id": posting_id}
    body.update(overrides)
    response = await client.post("/applications", headers=headers, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def test_applications_require_authentication(client: AsyncClient) -> None:
    """Where someone has applied is as personal as it gets."""
    assert (await client.get("/applications")).status_code == 401
    assert (await client.post("/applications", json={})).status_code == 401


async def test_recording_an_application_defaults_to_today(client: AsyncClient) -> None:
    """The common case is recording an application as it is sent."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)

    application = await apply(client, headers, posting_id)

    assert application["status"] == "applied"
    assert application["applied_at"] == date.today().isoformat()
    assert application["days_since_applied"] == 0
    assert application["needs_chasing"] is False


async def test_the_same_posting_cannot_be_applied_for_twice(
    client: AsyncClient,
) -> None:
    """A double-click is not a second application."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    await apply(client, headers, posting_id)

    response = await client.post(
        "/applications", headers=headers, json={"job_posting_id": posting_id}
    )

    assert response.status_code == 400


async def test_an_application_cannot_predate_being_sent(client: AsyncClient) -> None:
    """A future date would make every interval measured from it negative."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)

    response = await client.post(
        "/applications",
        headers=headers,
        json={
            "job_posting_id": posting_id,
            "applied_at": (date.today() + timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 422


async def test_another_users_posting_cannot_be_applied_for(
    client: AsyncClient,
) -> None:
    """The posting id comes from the client, so ownership is checked, not assumed."""
    owner = await register_and_login(client)
    posting_id = await save_posting(client, owner)

    intruder = await register_and_login(client, email="intruder@example.com")
    response = await client.post(
        "/applications", headers=intruder, json={"job_posting_id": posting_id}
    )

    assert response.status_code == 404


async def test_a_quiet_application_is_flagged_for_chasing(client: AsyncClient) -> None:
    """Silence is not a status. Time since it went out is what says to follow up."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)

    application = await apply(
        client,
        headers,
        posting_id,
        applied_at=(date.today() - timedelta(days=30)).isoformat(),
    )

    assert application["days_since_applied"] == 30
    assert application["needs_chasing"] is True


async def test_a_rejection_is_never_worth_chasing(client: AsyncClient) -> None:
    """A rejection is an answer. Nagging about it is how a feature gets ignored."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    application = await apply(
        client,
        headers,
        posting_id,
        applied_at=(date.today() - timedelta(days=30)).isoformat(),
    )

    response = await client.patch(
        f"/applications/{application['id']}",
        headers=headers,
        json={"status": "rejected"},
    )

    assert response.status_code == 200
    assert response.json()["needs_chasing"] is False
    assert response.json()["status_changed_at"] == date.today().isoformat()


async def test_amending_notes_does_not_reset_the_chase_clock(
    client: AsyncClient,
) -> None:
    """Fixing a typo must not make a three-week silence look like a fresh send."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    sent = date.today() - timedelta(days=30)
    application = await apply(client, headers, posting_id, applied_at=sent.isoformat())

    response = await client.patch(
        f"/applications/{application['id']}",
        headers=headers,
        json={"notes": "Spoke to the recruiter."},
    )

    assert response.json()["status_changed_at"] == sent.isoformat()
    assert response.json()["needs_chasing"] is True


async def test_reply_rate_ignores_applications_too_recent_to_have_been_answered(
    client: AsyncClient,
) -> None:
    """Counting this morning's application as unanswered would libel every live search.

    One old application with a reply and one sent today: the rate is 100%, not 50%.
    """
    headers = await register_and_login(client)
    old = await save_posting(client, headers, title="Backend Engineer")
    fresh = await save_posting(client, headers, title="Platform Engineer")

    answered = await apply(
        client,
        headers,
        old,
        applied_at=(date.today() - timedelta(days=30)).isoformat(),
    )
    await client.patch(
        f"/applications/{answered['id']}",
        headers=headers,
        json={"status": "interviewing"},
    )
    await apply(client, headers, fresh)

    stats = (await client.get("/applications/stats", headers=headers)).json()

    assert stats["total"] == 2
    assert stats["answerable"] == 1
    assert stats["replied"] == 1
    assert stats["reply_rate"] == 100


async def test_reply_rate_is_absent_rather_than_zero_before_anything_is_answerable(
    client: AsyncClient,
) -> None:
    """No rate yet and nobody replied are different facts about a search."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    await apply(client, headers, posting_id)

    stats = (await client.get("/applications/stats", headers=headers)).json()

    assert stats["answerable"] == 0
    assert stats["reply_rate"] is None


async def test_the_cv_that_was_sent_is_recorded(client: AsyncClient) -> None:
    """Reply rate per CV version is the only form of that number anyone can act on."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    cv_id = await upload_cv(client, headers)

    application = await apply(client, headers, posting_id, cv_id=cv_id)

    assert application["cv_id"] == cv_id


async def test_unapplied_lists_only_postings_with_no_application(
    client: AsyncClient,
) -> None:
    """The one list in the product that shrinks as the search progresses."""
    headers = await register_and_login(client)
    applied_for = await save_posting(client, headers, title="Backend Engineer")
    untouched = await save_posting(client, headers, title="Platform Engineer")
    await apply(client, headers, applied_for)

    response = await client.get("/applications/unapplied", headers=headers)

    assert [posting["id"] for posting in response.json()] == [untouched]


async def test_deleting_an_application_keeps_the_posting(client: AsyncClient) -> None:
    """Forgetting that you applied is not the same as losing interest in the role."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    application = await apply(client, headers, posting_id)

    response = await client.delete(
        f"/applications/{application['id']}", headers=headers
    )

    assert response.status_code == 204
    assert len((await client.get("/jobs", headers=headers)).json()) == 1
    assert (await client.get("/applications", headers=headers)).json() == []


async def test_applications_are_scoped_to_their_owner(client: AsyncClient) -> None:
    """One user's search must be invisible to another's."""
    owner = await register_and_login(client)
    posting_id = await save_posting(client, owner)
    application = await apply(client, owner, posting_id)

    intruder = await register_and_login(client, email="intruder@example.com")

    assert (await client.get("/applications", headers=intruder)).json() == []
    assert (
        await client.patch(
            f"/applications/{application['id']}",
            headers=intruder,
            json={"status": "offer"},
        )
    ).status_code == 404
