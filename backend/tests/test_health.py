from httpx import AsyncClient


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
