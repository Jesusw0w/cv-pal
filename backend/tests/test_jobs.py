import httpx
import pytest
from httpx import AsyncClient

from cv_pal.analysis.matching import MatchScore, score_posting
from cv_pal.constants import WorkRegime
from cv_pal.dependencies import get_http_client
from cv_pal.integrations.job_boards import board_for, strip_html
from cv_pal.main import app
from cv_pal.services.job_service import content_hash
from tests.helpers import register_and_login

POSTING = (
    "We are hiring a Senior Backend Engineer. Requirements: strong Python experience, "
    "PostgreSQL and Docker. This role is fully remote. Nice to have: Kubernetes."
)


async def save(
    client: AsyncClient, headers: dict[str, str], **overrides: object
) -> int:
    """Save a pasted posting and return its id."""
    body: dict[str, object] = {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "description": POSTING,
    }
    body.update(overrides)
    response = await client.post("/jobs/paste", headers=headers, json=body)
    posting_id: int = response.json()["id"]
    return posting_id


async def test_jobs_require_authentication(client: AsyncClient) -> None:
    """Saved postings are personal, so none of this is anonymous."""
    assert (await client.get("/jobs")).status_code == 401
    assert (await client.post("/jobs/paste", json={})).status_code == 401


async def test_a_pasted_posting_is_saved_and_scored(client: AsyncClient) -> None:
    """Paste is the route that always works, and a saved posting comes back scored."""
    headers = await register_and_login(client)
    await save(client, headers)

    response = await client.get("/jobs", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["posting"]["title"] == "Senior Backend Engineer"
    assert 0 <= body[0]["match"]["score"] <= 100
    # Every score is explainable — the reasons are what the number is made of.
    assert len(body[0]["match"]["reasons"]) == 4


async def test_the_same_posting_is_not_saved_twice(client: AsyncClient) -> None:
    """The same role reaches a user from several boards; it should collapse to one."""
    headers = await register_and_login(client)
    await save(client, headers)

    response = await client.post(
        "/jobs/paste",
        headers=headers,
        json={
            "title": "Senior Backend Engineer",
            "company": "Acme",
            "description": POSTING,
        },
    )

    assert response.status_code == 400
    assert "already saved" in response.text


async def test_a_short_paste_is_rejected(client: AsyncClient) -> None:
    """A stray paste is not a job posting."""
    headers = await register_and_login(client)

    response = await client.post(
        "/jobs/paste",
        headers=headers,
        json={"title": "Role", "description": "too short"},
    )

    assert response.status_code == 422


async def test_postings_are_per_user(client: AsyncClient) -> None:
    """One account's saved postings are invisible to another."""
    first = await register_and_login(client, email="one@example.com")
    second = await register_and_login(client, email="two@example.com")
    await save(client, first)

    assert (await client.get("/jobs", headers=second)).json() == []


async def test_deleting_a_posting_another_user_owns_is_a_404(
    client: AsyncClient,
) -> None:
    """Ownership is enforced in the query, so it simply does not exist."""
    owner = await register_and_login(client, email="owner@example.com")
    posting_id = await save(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.delete(f"/jobs/{posting_id}", headers=intruder)

    assert response.status_code == 404


# --- Importing a link ---


async def test_an_unrecognised_url_is_refused_and_points_at_paste(
    client: AsyncClient,
) -> None:
    """There is no general URL fetcher, and that is a decision rather than a gap.

    Fetching a user-supplied URL server-side is a request-forgery primitive: on a
    self-hosted install the API can usually reach the router, the cloud metadata
    endpoint, and every other service on the host. This test pins the refusal so the
    convenience is not quietly added later.
    """
    headers = await register_and_login(client)

    for url in (
        "https://acme.com/careers/12",
        "http://127.0.0.1:8000/health",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
    ):
        response = await client.post(
            "/jobs/import-url", headers=headers, json={"url": url}
        )
        assert response.status_code == 400, url
        assert "paste" in response.text.lower()


async def test_a_greenhouse_link_is_read_through_the_board_api(
    client: AsyncClient,
) -> None:
    """A sanctioned board is read through its own API, never by scraping."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "title": "Staff Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/4012345",
                "location": {"name": "Remote"},
                "content": "<p>Requirements: <strong>Python</strong> and Docker.</p>",
            },
        )

    transport = httpx.MockTransport(handler)

    async def fake_client() -> object:
        async with httpx.AsyncClient(transport=transport) as fake:
            yield fake

    app.dependency_overrides[get_http_client] = fake_client
    try:
        headers = await register_and_login(client)
        response = await client.post(
            "/jobs/import-url",
            headers=headers,
            json={"url": "https://boards.greenhouse.io/acme/jobs/4012345"},
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Staff Engineer"
    assert body["source"] == "greenhouse"
    # The board's own API, not the page the user pasted.
    assert requested == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/4012345"]
    # HTML is stripped, or the keyword analysis would report "strong" as a requirement.
    assert "<strong>" not in body["description"]


async def test_a_board_that_fails_is_reported_as_such(client: AsyncClient) -> None:
    """A board being down is not the user's fault, and paste still works."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)

    async def fake_client() -> object:
        async with httpx.AsyncClient(transport=transport) as fake:
            yield fake

    app.dependency_overrides[get_http_client] = fake_client
    try:
        headers = await register_and_login(client)
        response = await client.post(
            "/jobs/import-url",
            headers=headers,
            json={"url": "https://jobs.lever.co/acme/abc-123"},
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 502
    assert "paste" in response.text.lower()


# --- The pieces, in isolation ---


def test_only_sanctioned_boards_are_recognised() -> None:
    """The allowlist is the security boundary, so it is worth an explicit test."""
    assert board_for("https://boards.greenhouse.io/acme/jobs/1") is not None
    assert board_for("https://jobs.lever.co/acme/abc") is not None
    assert board_for("https://evil.example/greenhouse.io/acme/jobs/1") is None
    assert board_for("https://linkedin.com/jobs/view/123") is None


def test_html_is_reduced_to_words() -> None:
    """Tags left in a description become skills the posting appears to require."""
    text = strip_html("<p>Build <strong>things</strong>.</p><ul><li>Python</li></ul>")

    assert "<" not in text
    assert "Python" in text


def test_the_same_role_hashes_the_same_regardless_of_spacing() -> None:
    """Whitespace and case differ between boards; the role does not."""
    assert content_hash("Engineer", "Acme", "Build   things") == content_hash(
        "engineer", "ACME", "Build things"
    )


def test_a_non_negotiable_regime_blocks_rather_than_scores() -> None:
    """A user who ruled out on-site should not be shown a 74% match in an office.

    Blocking rather than penalising is the whole distinction between a non-negotiable
    and a preference — see PLANNING.md, principle 8.
    """
    result = score_posting(
        title="Backend Engineer",
        description="This role is on-site in our Munich office five days a week.",
        location="Munich",
        profile_text="Python PostgreSQL Docker",
        target_roles=["Backend Engineer"],
        work_regimes=[WorkRegime.REMOTE],
        regime_non_negotiable=True,
    )

    assert result.score == 0
    assert result.blocked_by is not None


def test_a_posting_that_does_not_state_its_arrangement_is_not_blocked() -> None:
    """Most postings never say. Blocking them would hide most of the market."""
    result = score_posting(
        title="Backend Engineer",
        description="Requirements: Python, PostgreSQL and Docker.",
        location=None,
        profile_text="Python PostgreSQL Docker",
        target_roles=["Backend Engineer"],
        work_regimes=[WorkRegime.REMOTE],
        regime_non_negotiable=True,
    )

    assert result.blocked_by is None
    assert result.score > 0


def test_unstated_target_roles_do_not_penalise_every_posting() -> None:
    """A preference the user never expressed cannot be failed."""
    scored = score_posting(
        title="Backend Engineer",
        description="Requirements: Python and Docker.",
        location=None,
        profile_text="Python Docker",
        target_roles=[],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    assert scored.score > 50


@pytest.mark.parametrize(
    ("title", "expected_at_least"),
    [("Senior Backend Engineer", 1.0), ("Frontend Designer", 0.0)],
)
def test_title_matching_tolerates_seniority_prefixes(
    title: str, expected_at_least: float
) -> None:
    """A seniority prefix should not stop a title matching its target role."""
    scored = score_posting(
        title=title,
        description="Requirements: Python.",
        location=None,
        profile_text="Python",
        target_roles=["Backend Engineer"],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    assert scored.score >= expected_at_least


# --- Watching a whole board ---


def board_transport(jobs: list[dict[str, object]]) -> httpx.MockTransport:
    """A Greenhouse board that returns `jobs`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": jobs})

    return httpx.MockTransport(handler)


def use_transport(transport: httpx.MockTransport) -> None:
    """Point the HTTP dependency at a transport that never touches the network."""

    async def fake_client() -> object:
        async with httpx.AsyncClient(transport=transport) as fake:
            yield fake

    app.dependency_overrides[get_http_client] = fake_client


async def connect(
    client: AsyncClient, headers: dict[str, str], *, filter_by_goals: bool = False
) -> int:
    """Watch a Greenhouse board and return the connection id."""
    response = await client.post(
        "/jobs/sources",
        headers=headers,
        json={
            "source": "greenhouse",
            "identifier": "acme",
            "filter_by_goals": filter_by_goals,
        },
    )
    connection_id: int = response.json()["id"]
    return connection_id


MIXED_BOARD = [
    {
        "id": 1,
        "title": "Senior Backend Engineer",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
        "content": "<p>Requirements: Python and Docker experience.</p>",
    },
    {
        "id": 2,
        "title": "Warehouse Operative",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
        "content": "<p>Requirements: forklift licence and heavy lifting.</p>",
    },
]


async def test_a_filtered_sync_saves_only_what_the_goals_ask_for(
    client: AsyncClient,
) -> None:
    """A company board is every open role, most of which are not the user's field.

    Until this existed, goals only changed how a saved posting ranked — so watching one
    company meant hand-filtering its warehouse vacancies out of a job search forever.
    """
    use_transport(board_transport(MIXED_BOARD))
    try:
        headers = await register_and_login(client)
        await client.put(
            "/profile/goals",
            headers=headers,
            json={"target_roles": ["Backend Engineer"]},
        )
        connection_id = await connect(client, headers, filter_by_goals=True)

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.json()["added"] == 1
    # Reported, not dropped quietly: the count is how the user notices a filter that is
    # tuned wrong for their search.
    assert response.json()["skipped"] == 1
    saved = (await client.get("/jobs", headers=headers)).json()
    assert [entry["posting"]["title"] for entry in saved] == ["Senior Backend Engineer"]


async def test_the_filter_does_nothing_until_it_is_asked_for(
    client: AsyncClient,
) -> None:
    """Off by default.

    A posting that never arrives is not one the user can go looking for.
    """
    use_transport(board_transport(MIXED_BOARD))
    try:
        headers = await register_and_login(client)
        await client.put(
            "/profile/goals",
            headers=headers,
            json={"target_roles": ["Backend Engineer"]},
        )
        connection_id = await connect(client, headers)

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.json()["added"] == 2
    assert response.json()["skipped"] == 0


async def test_a_filtered_sync_with_no_target_roles_saves_everything(
    client: AsyncClient,
) -> None:
    """An empty goal list is not a filter that rejects everything.

    It is the state every new account is in, and treating it as "match nothing" would
    make a watched board look permanently broken.
    """
    use_transport(board_transport(MIXED_BOARD))
    try:
        headers = await register_and_login(client)
        connection_id = await connect(client, headers, filter_by_goals=True)

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.json()["added"] == 2
    assert response.json()["skipped"] == 0


async def test_only_listable_boards_can_be_watched(client: AsyncClient) -> None:
    """A paste has no board behind it, so there is nothing to watch."""
    headers = await register_and_login(client)

    response = await client.post(
        "/jobs/sources",
        headers=headers,
        json={"source": "manual", "identifier": "acme"},
    )

    assert response.status_code == 400


async def test_a_board_identifier_cannot_reshape_the_request(
    client: AsyncClient,
) -> None:
    """The identifier is interpolated into an API path, so it is restricted.

    A permissive value would let a caller point the server's request somewhere else,
    which is the same class of problem the missing URL fetcher avoids.
    """
    headers = await register_and_login(client)

    for identifier in ("../../etc", "acme/../evil", "acme?x=1", "acme#f", "a b"):
        response = await client.post(
            "/jobs/sources",
            headers=headers,
            json={"source": "greenhouse", "identifier": identifier},
        )
        assert response.status_code == 422, identifier


async def test_syncing_saves_the_whole_board(client: AsyncClient) -> None:
    """One sync, every open posting."""
    use_transport(
        board_transport(
            [
                {
                    "id": 1,
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    "content": "<p>Requirements: Python and Docker experience.</p>",
                },
                {
                    "id": 2,
                    "title": "Frontend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                    "content": "<p>Requirements: TypeScript and React.</p>",
                },
            ]
        )
    )
    try:
        headers = await register_and_login(client)
        connection_id = await connect(client, headers)

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 200
    assert response.json() == {
        "connection_id": connection_id,
        "found": 2,
        "added": 2,
        "skipped": 0,
        "error": None,
    }
    assert len((await client.get("/jobs", headers=headers)).json()) == 2


async def test_syncing_twice_adds_nothing_the_second_time(
    client: AsyncClient,
) -> None:
    """Idempotent by content hash — which is what makes it safe on a timer.

    Without this, a nightly sync would grow the list by the size of the board every
    night, and scheduling would need de-duplication logic of its own.
    """
    use_transport(
        board_transport(
            [
                {
                    "id": 1,
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    "content": "<p>Requirements: Python and Docker experience.</p>",
                }
            ]
        )
    )
    try:
        headers = await register_and_login(client)
        connection_id = await connect(client, headers)

        first = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
        second = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert first.json()["added"] == 1
    assert second.json()["found"] == 1
    assert second.json()["added"] == 0
    assert len((await client.get("/jobs", headers=headers)).json()) == 1


async def test_an_unreachable_board_is_recorded_not_raised(
    client: AsyncClient,
) -> None:
    """One unreachable company must not fail a sweep across all of them."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    use_transport(httpx.MockTransport(handler))
    try:
        headers = await register_and_login(client)
        connection_id = await connect(client, headers)

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
        sources = (await client.get("/jobs/sources", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 200
    assert response.json()["error"] is not None
    assert response.json()["added"] == 0
    # Recorded on the connection so the user can see which board is failing.
    assert sources[0]["last_error"] is not None
    assert sources[0]["last_synced_at"] is not None


async def test_the_same_board_cannot_be_watched_twice(client: AsyncClient) -> None:
    """Two connections to one board would double every sync."""
    headers = await register_and_login(client)
    await connect(client, headers)

    response = await client.post(
        "/jobs/sources",
        headers=headers,
        json={"source": "greenhouse", "identifier": "acme"},
    )

    assert response.status_code == 400


async def test_connections_are_per_user(client: AsyncClient) -> None:
    """One account's watched boards are invisible to another."""
    first = await register_and_login(client, email="a@example.com")
    second = await register_and_login(client, email="b@example.com")
    connection_id = await connect(client, first)

    assert (await client.get("/jobs/sources", headers=second)).json() == []
    assert (
        await client.post(f"/jobs/sources/{connection_id}/sync", headers=second)
    ).status_code == 404


# --- Remotive: discovery rather than a company board ---

REMOTIVE_FEED: list[dict[str, object]] = [
    {
        "id": 2091088,
        "url": "https://remotive.com/remote-jobs/software-development/senior-python-2091088",
        "title": "Senior Python Engineer",
        "company_name": "Acme Remote ",
        "category": "Software Development",
        "job_type": "contract",
        "candidate_required_location": "Europe",
        "description": "<p>Requirements: Python, PostgreSQL and Docker.</p>",
    },
    {
        "id": 2091089,
        "url": "https://remotive.com/remote-jobs/devops/platform-engineer-2091089",
        "title": "Platform Engineer",
        "company_name": "Beta Co",
        "category": "Devops",
        "job_type": "full_time",
        "candidate_required_location": "Worldwide",
        "description": "<p>Requirements: Kubernetes and Terraform.</p>",
    },
    {
        "id": 2091090,
        "url": "https://remotive.com/remote-jobs/sales/sales-jedi-2091090",
        "title": "Sales Jedi",
        "company_name": "Gamma",
        "category": "Sales",
        "job_type": "",
        "candidate_required_location": "USA",
        "description": "<p>Requirements: a quota and a smile.</p>",
    },
]


def remotive_transport(
    requested: list[str] | None = None,
) -> httpx.MockTransport:
    """The Remotive feed, recording what was asked for."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(str(request.url))
        return httpx.Response(200, json={"jobs": REMOTIVE_FEED})

    return httpx.MockTransport(handler)


async def watch_remotive(
    client: AsyncClient, headers: dict[str, str], identifier: str
) -> int:
    """Watch one Remotive category and return the connection id."""
    response = await client.post(
        "/jobs/sources",
        headers=headers,
        json={"source": "remotive", "identifier": identifier},
    )
    connection_id: int = response.json()["id"]
    return connection_id


async def test_a_remotive_category_saves_only_that_category(
    client: AsyncClient,
) -> None:
    """The identifier is a category, not a company — and it must actually filter.

    Remotive's own `category` parameter is accepted and ignored, so the whole feed
    arrives every time and the filtering is ours. If it regressed, watching one
    category would silently save every remote job on the internet.
    """
    requested: list[str] = []
    use_transport(remotive_transport(requested))
    try:
        headers = await register_and_login(client)
        connection_id = await watch_remotive(client, headers, "software-development")

        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
        saved = (await client.get("/jobs", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 200
    assert response.json()["found"] == 1
    assert len(saved) == 1
    assert saved[0]["posting"]["title"] == "Senior Python Engineer"
    # No dead query parameters: sending `category` would imply it works.
    assert requested == ["https://remotive.com/api/remote-jobs"]


async def test_remotive_records_the_contract_on_offer(client: AsyncClient) -> None:
    """The contract type is the one thing this source states that the others cannot."""
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        connection_id = await watch_remotive(client, headers, "devops")
        await client.post(f"/jobs/sources/{connection_id}/sync", headers=headers)
        saved = (await client.get("/jobs", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert saved[0]["posting"]["employment_type"] == "full_time"


async def test_an_unstated_contract_is_null_not_full_time(
    client: AsyncClient,
) -> None:
    """The feed emits an empty string for "not stated", which is not a contract.

    Reading it as full time would be the app inventing the commonest answer, which is
    exactly the failure the nullable column exists to prevent.
    """
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        connection_id = await watch_remotive(client, headers, "sales")
        await client.post(f"/jobs/sources/{connection_id}/sync", headers=headers)
        saved = (await client.get("/jobs", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert saved[0]["posting"]["employment_type"] is None


async def test_a_remotive_posting_is_marked_remote(client: AsyncClient) -> None:
    """The feed is remote-only, so the location says so and the regime check reads it.

    Without this a remote-only user's non-negotiable has nothing to confirm against:
    the description does not always contain the word.
    """
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        connection_id = await watch_remotive(client, headers, "software-development")
        await client.post(f"/jobs/sources/{connection_id}/sync", headers=headers)
        saved = (await client.get("/jobs", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert saved[0]["posting"]["location"] == "Remote · Europe"


async def test_a_quiet_category_is_not_an_error(client: AsyncClient) -> None:
    """The feed holds only what is open now, so an empty category is a normal answer."""
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        connection_id = await watch_remotive(client, headers, "medical")
        response = await client.post(
            f"/jobs/sources/{connection_id}/sync", headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 200
    assert response.json() == {
        "connection_id": connection_id,
        "found": 0,
        "added": 0,
        "skipped": 0,
        "error": None,
    }


async def test_a_remotive_link_is_read_from_the_feed(client: AsyncClient) -> None:
    """There is no per-posting endpoint, so a link is resolved against the feed."""
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        response = await client.post(
            "/jobs/import-url",
            headers=headers,
            json={
                "url": "https://remotive.com/remote-jobs/devops/platform-engineer-2091089"
            },
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 201
    assert response.json()["title"] == "Platform Engineer"
    assert response.json()["employment_type"] == "full_time"


async def test_a_remotive_link_that_aged_out_points_at_paste(
    client: AsyncClient,
) -> None:
    """The feed is a stream, not an archive. An older link is unreachable, and says so.

    It surfaces as `JobBoardError` — the same 502 as a board that will not answer —
    rather than as "unsupported URL", which would be untrue: the link is one CV Pal
    reads, the posting behind it has simply rotated out. What is pinned here is the
    part the user acts on, which is identical for both: paste it instead.
    """
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        response = await client.post(
            "/jobs/import-url",
            headers=headers,
            json={"url": "https://remotive.com/remote-jobs/devops/gone-1000000"},
        )
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 502
    assert "paste" in response.text.lower()


# --- Where the user may work ---


def score_where(
    location: str | None,
    work_locations: list[str],
    *,
    non_negotiable: bool = False,
) -> MatchScore:
    """Score a posting that differs only in where it says you must be."""
    return score_posting(
        title="Backend Engineer",
        description="Requirements: Python, PostgreSQL and Docker. Fully remote.",
        location=location,
        profile_text="Python PostgreSQL Docker",
        target_roles=["Backend Engineer"],
        work_regimes=[WorkRegime.REMOTE],
        regime_non_negotiable=False,
        work_locations=work_locations,
        location_non_negotiable=non_negotiable,
    )


def test_a_remote_role_in_another_continent_is_not_a_match() -> None:
    """The defect discovery introduced: "Remote · Brazil" is remote and still unusable.

    Before this, such a posting was scored on skills alone and ranked alongside jobs the
    user could actually take — the source got better at finding roles and the ranking
    got worse at ordering them.
    """
    result = score_where("Remote · Brazil", ["Portugal", "Europe"])

    assert result.blocked_by is None, "a preference, not a filter, until it is set so"
    assert any(
        "not where you said you can work" in reason.detail for reason in result.reasons
    )


def test_where_you_can_work_blocks_when_it_is_non_negotiable() -> None:
    """Same distinction as the regime: a non-negotiable filters, it does not rank."""
    result = score_where("Remote · Brazil", ["Portugal", "Europe"], non_negotiable=True)

    assert result.score == 0
    assert result.blocked_by is not None
    assert "Brazil" in result.blocked_by


def test_a_region_the_user_listed_matches_the_posting_that_names_it() -> None:
    """The user lists their own regions; nothing here infers that Portugal is in Europe.

    That is the point of asking rather than deriving — the project has no authoritative
    containment data, and a guess about the world hides jobs silently.
    """
    result = score_where("Remote · Europe", ["Portugal", "Europe"], non_negotiable=True)

    assert result.blocked_by is None
    assert any("where you said you can work" in r.detail for r in result.reasons)


def test_an_inflected_region_still_matches() -> None:
    """Feeds inflect freely: "European timezones" is the same place as "Europe"."""
    result = score_where(
        "Remote · UK, Germany, France, European timezones",
        ["Europe"],
        non_negotiable=True,
    )

    assert result.blocked_by is None


def test_worldwide_satisfies_everyone() -> None:
    """A posting that restricts nobody cannot exclude anybody."""
    result = score_where("Remote · Worldwide", ["Portugal"], non_negotiable=True)

    assert result.blocked_by is None
    assert any("anywhere" in r.detail for r in result.reasons)


def test_remote_on_its_own_names_nowhere_and_never_blocks() -> None:
    """A bare "Remote" is an arrangement, not a place.

    Without this, a feed that writes bare "Remote" would read as a country nobody lives
    in and block every posting it published.
    """
    result = score_where("Remote", ["Portugal"], non_negotiable=True)

    assert result.blocked_by is None
    assert any("does not say where" in r.detail for r in result.reasons)


def test_a_posting_with_no_location_is_never_blocked() -> None:
    """Silence is not evidence the user cannot be there — same rule as the regime."""
    result = score_where(None, ["Portugal"], non_negotiable=True)

    assert result.blocked_by is None


def test_saying_nothing_about_where_you_can_work_penalises_nothing() -> None:
    """An unstated preference cannot be failed."""
    anywhere = score_where("Remote · Brazil", [])
    listed = score_where("Remote · Brazil", ["Brazil"])

    assert anywhere.blocked_by is None
    assert anywhere.score == listed.score


async def test_syncing_everything_at_once_is_one_call(client: AsyncClient) -> None:
    """The endpoint a cron entry calls: one line that survives the watch list changing.

    Per-connection sync needs the ids up front, so a nightly entry meant one command per
    source and a rewrite whenever the user watched another.
    """
    use_transport(remotive_transport())
    try:
        headers = await register_and_login(client)
        await watch_remotive(client, headers, "software-development")
        await watch_remotive(client, headers, "devops")

        response = await client.post("/jobs/sources/sync", headers=headers)
        saved = (await client.get("/jobs", headers=headers)).json()
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert sum(result["added"] for result in body) == 2
    assert len(saved) == 2


async def test_sync_all_is_not_read_as_a_connection_id(client: AsyncClient) -> None:
    """`/sources/sync` must not be matched by `/sources/{connection_id}/sync`.

    Route order is the only thing separating them, so it is worth pinning: the wrong
    order answers 422 for a path that should work.
    """
    headers = await register_and_login(client)

    response = await client.post("/jobs/sources/sync", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_one_unreachable_source_does_not_abort_the_sweep(
    client: AsyncClient,
) -> None:
    """A board being down is recorded against it, and the others still sync."""

    def handler(request: httpx.Request) -> httpx.Response:
        # The Greenhouse board fails; the Remotive feed answers.
        if "greenhouse" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, json={"jobs": REMOTIVE_FEED})

    use_transport(httpx.MockTransport(handler))
    try:
        headers = await register_and_login(client)
        await connect(client, headers)
        await watch_remotive(client, headers, "devops")

        response = await client.post("/jobs/sources/sync", headers=headers)
    finally:
        app.dependency_overrides.pop(get_http_client, None)

    body = response.json()
    assert len(body) == 2
    assert [result["error"] is not None for result in body] == [True, False]
    assert body[1]["added"] == 1


def test_an_unscored_profile_does_not_read_as_a_moderate_match() -> None:
    """A brand-new user used to see 40/100 against every posting.

    Title, arrangement and location each scored a perfect 1.0 when the user had stated
    no preference, so 40% of the weight was handed over for free and the ranking
    collapsed to a constant. Zero is the true answer here, and the reasons say why.
    """
    scored = score_posting(
        title="Senior Golang Developer",
        description="We need Go, Kubernetes and PostgreSQL.",
        location="Remote",
        profile_text="",
        target_roles=[],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    assert scored.score == 0
    assert [r.label for r in scored.reasons if "not scored" in r.label] == [
        "Title — not scored",
        "Work arrangement — not scored",
        "Where you can work — not scored",
    ]


def test_the_score_renormalises_over_what_it_could_judge() -> None:
    """Perfect coverage with nothing else stated is 100, not 60."""
    scored = score_posting(
        title="Backend Engineer",
        description="Requirements: Python and Docker.",
        location=None,
        profile_text="Python Docker",
        target_roles=[],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    assert scored.score == 100


def test_a_stated_preference_that_fails_still_costs_the_posting() -> None:
    """Dropping unjudged components must not also drop judged ones."""
    scored = score_posting(
        title="Frontend Designer",
        description="Requirements: Python and Docker.",
        location=None,
        profile_text="Python Docker",
        target_roles=["Backend Engineer"],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    # Coverage 1.0 at weight .6, title 0.0 at weight .2, renormalised over .8.
    assert scored.score == 75


def test_the_hiring_company_is_not_a_missing_requirement() -> None:
    """The company name reaches scoring too, not just extraction."""
    scored = score_posting(
        title="Senior Engineer",
        description="A.Team is hiring. Requirements: Go and Kubernetes at A.Team.",
        location=None,
        company="A.Team",
        profile_text="Go Kubernetes",
        target_roles=[],
        work_regimes=[],
        regime_non_negotiable=False,
    )

    assert "a.team" not in scored.missing_required
