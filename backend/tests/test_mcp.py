"""The MCP endpoint, exercised over HTTP the way an agent reaches it.

Through the mounted app rather than an in-memory client, because the part most worth
testing — who may call what — lives in the HTTP layer an in-memory client skips.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from httpx import AsyncClient
from mcp.types import EmbeddedResource
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from cv_pal.config import Settings
from cv_pal.constants import DEFAULT_DOCX_MEDIA_TYPE
from cv_pal.main import app
from cv_pal.mcp.app import mcp_app
from cv_pal.mcp.runtime import hooks
from cv_pal.models import ApiToken
from tests.conftest import FakeLLMClient
from tests.helpers import DEFAULT_TEST_PASSWORD, register_and_login, upload_cv

POSTING = {
    "title": "Backend Engineer",
    "company": "Acme",
    "location": "Remote",
    "description": (
        "We are hiring a backend engineer to build Python and FastAPI services. "
        "Required: Python, PostgreSQL. Nice to have: Kubernetes."
    ),
}

READ_TOOLS = {
    "get_profile",
    "get_goals",
    "list_cvs",
    "check_cv",
    "propose_profile_from_cv",
    "list_job_postings",
    "get_job_posting",
    "tailor_cv",
    "export_tailored_cv",
    "draft_cover_letter",
    "list_applications",
    "get_application_stats",
    "review_linkedin_profile",
    "list_platforms",
}
WRITE_TOOLS = {
    "save_job_posting",
    "import_job_posting",
    "record_application",
    "update_application",
    "add_platform",
    "update_platform",
    "delete_platform",
}
PROFILE_TOOLS = {
    "update_profile",
    "set_goals",
    "add_experience",
    "update_experience",
    "delete_experience",
    "add_education",
    "update_education",
    "delete_education",
    "add_skill",
    "update_skill",
    "delete_skill",
    "add_language",
    "update_language",
    "delete_language",
    "add_portfolio_item",
    "update_portfolio_item",
    "delete_portfolio_item",
}
# Removing or overwriting what the user entered: a client should confirm these.
DESTRUCTIVE_TOOLS = {
    "delete_language",
    "delete_portfolio_item",
    "delete_platform",
    "set_goals",
    "delete_experience",
    "delete_education",
    "delete_skill",
}

ClientFor = Callable[[str | None], Client[StreamableHttpTransport]]


def _asgi_factory(
    headers: dict[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    auth: httpx2.Auth | None = None,
    follow_redirects: bool = False,
) -> httpx2.AsyncClient:
    """Build the MCP client's HTTP client against the app, in process."""
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://localhost",
        headers=headers,
        timeout=timeout,
        auth=auth,
        follow_redirects=follow_redirects,
    )


@pytest.fixture
def mcp_settings(test_settings: Settings) -> Settings:
    """Settings with the endpoint on, and local_only off: the two exclude each other."""
    return test_settings.model_copy(update={"mcp_enabled": True, "local_only": False})


@pytest.fixture
async def mcp_client(
    client: AsyncClient,
    db_session: AsyncSession,
    mcp_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[ClientFor]:
    """Wire the MCP side to the test database, and hand out clients per token.

    Depends on `client` so the HTTP API shares the same database and overrides.
    """

    @asynccontextmanager
    async def session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(hooks, "session_factory", session)
    monkeypatch.setattr(hooks, "settings", lambda: mcp_settings)

    def make(token: str | None) -> Client[StreamableHttpTransport]:
        return Client(
            StreamableHttpTransport(
                "http://localhost/mcp/",
                auth=token,
                httpx_client_factory=_asgi_factory,
            )
        )

    # The session manager's task group must be entered and exited by one task, and
    # pytest sets a fixture up and tears it down in different ones.
    started, stop = asyncio.Event(), asyncio.Event()

    async def serve() -> None:
        async with mcp_app.router.lifespan_context(mcp_app):
            started.set()
            await stop.wait()

    server = asyncio.create_task(serve())
    await started.wait()
    yield make
    stop.set()
    await server


async def issue_token(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    write: bool = False,
    edit_profile: bool = False,
    password: str = DEFAULT_TEST_PASSWORD,
) -> str:
    """Create a personal access token through the API and return its secret."""
    response = await client.post(
        "/users/me/tokens",
        headers=headers,
        json={
            "name": "agent",
            "password": password,
            "write": write,
            "edit_profile": edit_profile,
        },
    )
    assert response.status_code == 201, response.text
    token: str = response.json()["token"]
    return token


async def save_posting(client: AsyncClient, headers: dict[str, str]) -> int:
    """Save the test posting through the API and return its id."""
    response = await client.post("/jobs/paste", headers=headers, json=POSTING)
    assert response.status_code == 201, response.text
    posting_id: int = response.json()["id"]
    return posting_id


async def raw_post(token: str | None) -> httpx2.Response:
    """Send one bare MCP request, to see the HTTP answer rather than the client's."""
    headers = {"Accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    async with _asgi_factory() as http:
        return await http.post(
            "/mcp/",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )


# --- Who may connect ------------------------------------------------------------------


async def test_endpoint_is_off_unless_enabled(
    mcp_client: ClientFor, monkeypatch: pytest.MonkeyPatch, test_settings: Settings
) -> None:
    """A second way in exists only when the operator asks for it."""
    monkeypatch.setattr(hooks, "settings", lambda: test_settings)

    assert (await raw_post(None)).status_code == 404


async def test_no_token_is_refused(mcp_client: ClientFor) -> None:
    """Unauthenticated requests are answered with a bearer challenge."""
    response = await raw_post(None)

    assert response.status_code == 401
    assert "Bearer" in response.headers["www-authenticate"]


async def test_a_session_token_is_not_an_agent_token(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """The browser's access token does not open the MCP endpoint."""
    headers = await register_and_login(client)

    response = await raw_post(headers["Authorization"].removeprefix("Bearer "))

    assert response.status_code == 401


async def test_an_agent_token_is_not_a_session_token(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """A personal access token does not open the HTTP API: it is for agents only."""
    token = await issue_token(client, await register_and_login(client))

    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_revoked_token_stops_working(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Revoking cuts an agent off on its next request."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers)
    assert (await raw_post(token)).status_code == 200

    token_id = (await client.get("/users/me/tokens", headers=headers)).json()["tokens"][
        0
    ]["id"]
    await client.delete(f"/users/me/tokens/{token_id}", headers=headers)

    assert (await raw_post(token)).status_code == 401


async def test_expired_token_stops_working(
    client: AsyncClient, mcp_client: ClientFor, db_session: AsyncSession
) -> None:
    """Every token expires, and an expired one is refused like an unknown one."""
    token = await issue_token(client, await register_and_login(client))
    await db_session.execute(
        update(ApiToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db_session.commit()

    assert (await raw_post(token)).status_code == 401


async def test_password_change_revokes_agent_tokens(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Changing the password is what a user does when they fear a leak."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers)

    await client.patch(
        "/users/me/password",
        headers=headers,
        json={
            "current_password": DEFAULT_TEST_PASSWORD,
            "new_password": "a-completely-new-passphrase-9",
        },
    )

    assert (await raw_post(token)).status_code == 401


# --- Managing tokens ------------------------------------------------------------------


async def test_creating_a_token_needs_the_password(client: AsyncClient) -> None:
    """A stolen session cannot mint a long-lived credential."""
    headers = await register_and_login(client)

    response = await client.post(
        "/users/me/tokens",
        headers=headers,
        json={"name": "agent", "password": "not-the-password"},
    )

    assert response.status_code == 401


async def test_listing_never_shows_the_secret(
    client: AsyncClient, mcp_settings: Settings
) -> None:
    """The secret is shown once, at creation, and never again."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers)

    listed = (await client.get("/users/me/tokens", headers=headers)).json()

    assert token not in str(listed)
    assert listed["tokens"][0]["display_hint"] == token.removeprefix("cvp_")[:8]
    assert listed["tokens"][0]["scopes"] == "cvpal:read"


async def test_tokens_are_capped(client: AsyncClient) -> None:
    """A user cannot accumulate an unbounded number of credentials."""
    headers = await register_and_login(client)
    for _ in range(10):
        await issue_token(client, headers)

    response = await client.post(
        "/users/me/tokens",
        headers=headers,
        json={"name": "one too many", "password": DEFAULT_TEST_PASSWORD},
    )

    assert response.status_code == 400


def test_local_only_and_mcp_cannot_both_be_on(test_settings: Settings) -> None:
    """An agent's model may be hosted, so the endpoint and local-only mode conflict."""
    with pytest.raises(ValueError, match="local_only"):
        Settings.model_validate(
            {**test_settings.model_dump(), "mcp_enabled": True, "local_only": True}
        )


# --- What a token can do --------------------------------------------------------------


async def test_read_token_sees_only_read_tools(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """A tool the token may not call is not even offered to the agent."""
    token = await issue_token(client, await register_and_login(client))

    async with mcp_client(token) as agent:
        names = {tool.name for tool in await agent.list_tools()}

    assert names == READ_TOOLS


async def test_write_token_sees_every_tool(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Write scope adds the recording tools and nothing that edits the profile."""
    token = await issue_token(client, await register_and_login(client), write=True)

    async with mcp_client(token) as agent:
        names = {tool.name for tool in await agent.list_tools()}

    assert names == READ_TOOLS | WRITE_TOOLS


async def test_profile_token_adds_the_editing_tools(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Profile editing is its own grant, not implied by write and not implying it."""
    token = await issue_token(
        client, await register_and_login(client), edit_profile=True
    )

    async with mcp_client(token) as agent:
        names = {tool.name for tool in await agent.list_tools()}

    assert names == READ_TOOLS | PROFILE_TOOLS


async def test_write_token_cannot_edit_the_profile(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Recording postings is not permission to change what CVs are built from."""
    token = await issue_token(client, await register_and_login(client), write=True)

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError):
            await agent.call_tool("update_profile", {"changes": {"headline": "Hacked"}})


async def test_read_token_cannot_call_a_write_tool(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Hiding a tool is not the control: calling it by name is refused too."""
    token = await issue_token(client, await register_and_login(client))

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError):
            await agent.call_tool("save_job_posting", POSTING)


async def test_tools_are_annotated_for_the_client(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Clients decide what to confirm with the user from these hints."""
    token = await issue_token(client, await register_and_login(client), write=True)

    async with mcp_client(token) as agent:
        tools = {tool.name: tool for tool in await agent.list_tools()}

    for name in READ_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.read_only_hint is True, name
    for name in WRITE_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.read_only_hint is False, name
        assert annotations.destructive_hint is (name in DESTRUCTIVE_TOOLS), name


async def test_editing_tools_flag_what_destroys(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Deleting a record or replacing the goals is marked for confirmation."""
    token = await issue_token(
        client, await register_and_login(client), edit_profile=True
    )

    async with mcp_client(token) as agent:
        tools = {tool.name: tool for tool in await agent.list_tools()}

    for name in PROFILE_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.read_only_hint is False, name
        assert annotations.destructive_hint is (name in DESTRUCTIVE_TOOLS), name


# --- The tools ------------------------------------------------------------------------


async def test_postings_are_listed_scored_and_without_descriptions(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """The list is for choosing; the full text comes from get_job_posting."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    token = await issue_token(client, headers)

    async with mcp_client(token) as agent:
        listed = await agent.call_tool("list_job_postings", {})
        full = await agent.call_tool("get_job_posting", {"posting_id": posting_id})

    assert isinstance(listed.structured_content, dict)
    [summary] = listed.structured_content["result"]
    assert summary["id"] == posting_id
    assert "description" not in summary
    assert 0 <= summary["score"] <= 100
    assert full.structured_content is not None
    assert full.structured_content["posting"]["description"] == POSTING["description"]


async def test_tailored_cv_reports_gaps_rather_than_filling_them(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Grounded as in the interface: a skill the profile lacks comes back as a gap."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    token = await issue_token(client, headers)

    async with mcp_client(token) as agent:
        result = await agent.call_tool("tailor_cv", {"posting_id": posting_id})

    tailored = result.structured_content
    assert tailored is not None
    assert "PostgreSQL" not in tailored["markdown"]
    assert tailored["gaps"]


async def test_export_returns_a_docx_file(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """The file an application form wants, as an embedded resource."""
    headers = await register_and_login(client)
    posting_id = await save_posting(client, headers)
    token = await issue_token(client, headers)

    async with mcp_client(token) as agent:
        result = await agent.call_tool(
            "export_tailored_cv", {"posting_id": posting_id, "file_format": "docx"}
        )

    [content] = result.content
    assert isinstance(content, EmbeddedResource)
    assert content.resource.mime_type == DEFAULT_DOCX_MEDIA_TYPE


async def test_cv_tools_read_an_uploaded_cv(
    client: AsyncClient, mcp_client: ClientFor, fake_llm: FakeLLMClient
) -> None:
    """Checking and reading a CV work, and never run CV Pal's own model."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    token = await issue_token(client, headers)

    async with mcp_client(token) as agent:
        checked = await agent.call_tool(
            "check_cv", {"cv_id": cv_id, "job_description": POSTING["description"]}
        )
        proposed = await agent.call_tool("propose_profile_from_cv", {"cv_id": cv_id})

    assert checked.structured_content is not None
    assert checked.structured_content["coverage"] is not None
    assert proposed.structured_content is not None
    assert fake_llm.calls == []


async def test_timestamps_carry_their_zone(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Tools declare RFC 3339 `date-time`, which needs an offset.

    SQLite hands timestamps back naive; sent as they were, Claude Code rejected the
    whole `list_cvs` answer, which left the agent without a CV id for any other tool.
    """
    headers = await register_and_login(client)
    await upload_cv(client, headers)
    token = await issue_token(client, headers)

    async with mcp_client(token) as agent:
        listed = await agent.call_tool("list_cvs", {})

    assert listed.structured_content is not None
    created = listed.structured_content["result"][0]["created_at"]
    assert datetime.fromisoformat(created).tzinfo is not None


async def test_another_users_posting_does_not_exist(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Ownership holds through the agent exactly as through the API."""
    owner = await register_and_login(client, email="owner@example.com")
    posting_id = await save_posting(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")
    token = await issue_token(client, intruder)

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError, match="not found"):
            await agent.call_tool("get_job_posting", {"posting_id": posting_id})


async def test_write_token_records_an_application(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Saving a posting and logging an application: what an agent may record."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers, write=True)

    async with mcp_client(token) as agent:
        saved = await agent.call_tool("save_job_posting", POSTING)
        assert saved.structured_content is not None
        posting_id = saved.structured_content["id"]
        recorded = await agent.call_tool(
            "record_application", {"posting_id": posting_id}
        )
        assert recorded.structured_content is not None
        moved = await agent.call_tool(
            "update_application",
            {
                "application_id": recorded.structured_content["id"],
                "status": "interviewing",
            },
        )

    assert moved.structured_content is not None
    assert moved.structured_content["status"] == "interviewing"
    listed = (await client.get("/applications", headers=headers)).json()
    assert [item["status"] for item in listed] == ["interviewing"]


async def test_import_refuses_an_arbitrary_url(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """The agent inherits the no-general-fetcher rule: no request is made at all."""
    token = await issue_token(client, await register_and_login(client), write=True)

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError):
            await agent.call_tool(
                "import_job_posting", {"url": "http://169.254.169.254/latest/"}
            )


# --- Editing the profile ------------------------------------------------------------


async def test_an_agent_fills_in_the_profile_and_goals(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """What the agent writes is what the app shows: same handlers, same records."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers, edit_profile=True)

    async with mcp_client(token) as agent:
        await agent.call_tool(
            "update_profile", {"changes": {"headline": "Platform Engineer"}}
        )
        role = await agent.call_tool(
            "add_experience",
            {
                "role": {
                    "organisation": "Globex Corporation",
                    "title": "Staff Engineer",
                    "start_date": "2020-01-01",
                    "description": "Runs the Go deployment tooling.",
                }
            },
        )
        assert role.structured_content is not None
        role_id = role.structured_content["id"]
        await agent.call_tool(
            "add_skill", {"skill": {"name": "Go", "evidence_experience_ids": [role_id]}}
        )
        await agent.call_tool(
            "add_education",
            {"course": {"institution": "University of Leeds", "qualification": "BSc"}},
        )
        await agent.call_tool(
            "set_goals",
            {
                "goals": {
                    "target_roles": ["Platform Engineer"],
                    "work_regimes": ["remote"],
                }
            },
        )

    profile = (await client.get("/profile", headers=headers)).json()
    assert profile["headline"] == "Platform Engineer"
    assert [e["title"] for e in profile["experiences"]] == ["Staff Engineer"]
    assert profile["skills"][0]["evidence_experience_ids"] == [role_id]
    assert profile["educations"][0]["institution"] == "University of Leeds"
    goals = (await client.get("/profile/goals", headers=headers)).json()
    assert goals["target_roles"] == ["Platform Engineer"]


async def test_an_update_changes_only_the_fields_given(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """A partial update from an agent must not blank the fields it left out."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers, edit_profile=True)

    async with mcp_client(token) as agent:
        role = await agent.call_tool(
            "add_experience",
            {
                "role": {
                    "organisation": "Initech",
                    "title": "QA Tester",
                    "start_date": "2010-06-01",
                    "description": "Filed regressions.",
                }
            },
        )
        assert role.structured_content is not None
        await agent.call_tool(
            "update_experience",
            {
                "experience_id": role.structured_content["id"],
                "changes": {"title": "Senior QA Tester"},
            },
        )

    stored = (await client.get("/profile", headers=headers)).json()["experiences"][0]
    assert stored["title"] == "Senior QA Tester"
    assert stored["description"] == "Filed regressions."


async def test_an_agent_is_held_to_the_apps_validation(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """A role that ends before it starts is refused here as it is in the form."""
    token = await issue_token(
        client, await register_and_login(client), edit_profile=True
    )

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError):
            await agent.call_tool(
                "add_experience",
                {
                    "role": {
                        "organisation": "Initech",
                        "title": "QA Tester",
                        "start_date": "2012-01-01",
                        "end_date": "2010-01-01",
                    }
                },
            )


async def test_an_agent_cannot_delete_another_users_record(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """Ownership is checked by the same handler as the app's."""
    owner = await register_and_login(client)
    created = await client.post(
        "/profile/experiences",
        headers=owner,
        json={
            "organisation": "Hooli",
            "title": "Assistant",
            "start_date": "2009-07-01",
        },
    )
    intruder = await register_and_login(client, email="intruder@example.com")
    token = await issue_token(client, intruder, edit_profile=True)

    async with mcp_client(token) as agent:
        with pytest.raises(ToolError, match="not found"):
            await agent.call_tool(
                "delete_experience", {"experience_id": created.json()["id"]}
            )

    assert len((await client.get("/profile", headers=owner)).json()["experiences"]) == 1


async def test_an_application_can_be_recorded_without_a_saved_posting(
    client: AsyncClient, mcp_client: ClientFor
) -> None:
    """A recruiter's call has no posting to save; the agent must not invent one."""
    headers = await register_and_login(client)
    token = await issue_token(client, headers, write=True)

    async with mcp_client(token) as agent:
        recorded = await agent.call_tool(
            "record_application",
            {
                "role": {"title": "Python Developer", "company": "Initech"},
                "salary": "€40-45k",
                "next_step": "Technical interview",
            },
        )
        with pytest.raises(ToolError, match="either a saved posting or the role"):
            await agent.call_tool("record_application", {})

    assert recorded.structured_content is not None
    assert recorded.structured_content["title"] == "Python Developer"
    assert recorded.structured_content["next_step"] == "Technical interview"
