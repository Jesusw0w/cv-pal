from httpx import AsyncClient

from tests.conftest import FakeLLMClient
from tests.helpers import register_and_login


async def test_health(client: AsyncClient) -> None:
    """The health alias reports ok."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_live(client: AsyncClient) -> None:
    """The liveness probe reports ok."""
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_ready(client: AsyncClient) -> None:
    """The readiness probe reports ok when the database is reachable."""
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"


async def test_llm_status_reports_an_available_model(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """A usable model is reported by name."""
    headers = await register_and_login(client)

    response = await client.get("/health/llm", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "fake-model", "detail": None}


async def test_llm_status_says_what_is_wrong(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """A missing model is a reported state, not a failed request."""
    headers = await register_and_login(client)
    fake_llm.unavailable = "The model 'fake-model' is not available from the provider."

    response = await client.get("/health/llm", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "not available" in response.json()["detail"]


async def test_llm_status_needs_a_session(client: AsyncClient) -> None:
    """It names the model, so it is not public."""
    assert (await client.get("/health/llm")).status_code == 401
