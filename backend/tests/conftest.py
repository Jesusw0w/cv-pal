import json
import os
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

# Settings are validated at import time and secret_key has no default by design, so
# the environment must be primed before anything under cv_pal is imported.
os.environ.setdefault("CV_PAL_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CV_PAL_LLM_PROVIDER", "ollama")
os.environ.setdefault("CV_PAL_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from cv_pal.config import Settings, get_settings
from cv_pal.constants import LLMProvider
from cv_pal.database import get_db
from cv_pal.llm import get_llm_client
from cv_pal.main import app
from cv_pal.models import Base
from cv_pal.rate_limit import InMemoryRateLimiter, get_rate_limiter

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeLLMClient:
    """An LLM client that returns canned output instead of calling a model.

    Tests must never depend on a running Ollama server or a hosted API, so the real
    client is replaced wholesale via dependency override.
    """

    def __init__(self) -> None:
        """Initialise with a default valid response."""
        self.response: str = json.dumps(
            {
                "suggestions": [
                    {"type": "content", "content": "Quantify the migration project."},
                    {"type": "keywords", "content": "Surface 'Kubernetes' explicitly."},
                ]
            }
        )
        self.calls: list[tuple[str, str]] = []

    @property
    def model(self) -> str:
        """Return the fake model identifier.

        Returns:
            A fixed identifier.
        """
        return "fake-model"

    async def complete_json(self, *, system: str, user: str) -> str:
        """Record the call and return the configured response.

        Args:
            system: The system prompt.
            user: The user prompt.

        Returns:
            The canned response.
        """
        self.calls.append((system, user))
        return self.response


@pytest.fixture
def test_settings() -> Settings:
    """Provide settings that never reach a real provider or the developer's database.

    Returns:
        Settings for the test run.
    """
    return Settings(
        secret_key=SecretStr("test-secret-key"),
        database_url=TEST_DATABASE_URL,
        llm_provider=LLMProvider.OLLAMA,
        llm_base_url="http://localhost:11434/v1",
        local_only=True,
    )


@pytest.fixture
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession]:
    """Provide a session backed by a fresh in-memory schema.

    A StaticPool keeps every connection pointed at the same in-memory database, which
    would otherwise be discarded as soon as the first connection closed.

    Args:
        test_settings: Test settings selecting the in-memory database.

    Yields:
        An async session bound to the test schema.
    """
    engine = create_async_engine(
        test_settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """Provide the fake LLM client used by the app during tests.

    Returns:
        A fresh fake client.
    """
    return FakeLLMClient()


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    """Provide a rate limiter isolated to a single test.

    The application's limiter is process-wide state; without a fresh instance per test
    the counters would leak between tests and make them order-dependent.

    Returns:
        A limiter with the production defaults.
    """
    return InMemoryRateLimiter()


@pytest.fixture
async def client(
    db_session: AsyncSession,
    fake_llm: FakeLLMClient,
    test_settings: Settings,
    limiter: InMemoryRateLimiter,
) -> AsyncGenerator[AsyncClient]:
    """Provide an HTTP client bound to the app with test dependencies injected.

    Args:
        db_session: The test database session.
        fake_llm: The fake LLM client.
        test_settings: Test settings.
        limiter: The per-test rate limiter.

    Yields:
        An async HTTP client speaking to the application in-process.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect uploads to a temporary directory for every test.

    Args:
        tmp_path: Pytest-provided temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    Yields:
        The temporary upload directory.
    """
    target = tmp_path / "uploads"
    target.mkdir()
    # Exercised through real configuration rather than by patching a constant, so the
    # env-var path the container relies on is the one under test.
    monkeypatch.setenv("CV_PAL_UPLOAD_DIR", str(target))
    get_settings.cache_clear()
    yield target
    get_settings.cache_clear()
