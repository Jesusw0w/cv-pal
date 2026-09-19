import anthropic
import pytest
from pydantic import SecretStr

from cv_pal.config import Settings
from cv_pal.constants import LLMProvider
from cv_pal.exceptions import LLMError
from cv_pal.llm import AnthropicClient, OpenAICompatibleClient


def settings_for(provider: LLMProvider, **overrides: object) -> Settings:
    """Build settings for one provider without touching the environment."""
    # Explicitly blank, because the test environment primes CV_PAL_LLM_* for Ollama and
    # Settings reads it — the point here is the per-provider fallback.
    base: dict[str, object] = {
        "secret_key": SecretStr("test-secret"),
        "llm_provider": provider,
        "llm_api_key": SecretStr("test-key"),
        "llm_model": "",
        "llm_base_url": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class FakeMessages:
    """Stands in for `client.messages`, returning a canned response."""

    def __init__(self, response: object) -> None:
        """Hold the response, or the exception, that `create` should produce."""
        self._response = response
        self.kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> object:
        """Record what was sent and return the canned response.

        Args:
            **kwargs: The request the client built.

        Returns:
            The canned response.

        Raises:
            Exception: The canned exception, when one was given.
        """
        self.kwargs = kwargs
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class Block:
    """One content block of a response."""

    def __init__(self, text: str, type_: str = "text") -> None:
        """Initialise a block.

        Args:
            text: The block's text.
            type_: The block type, so non-text blocks can be exercised.
        """
        self.text = text
        self.type = type_


class Response:
    """A response, shaped like the SDK's."""

    def __init__(self, blocks: list[Block], stop_reason: str = "end_turn") -> None:
        """Initialise a response.

        Args:
            blocks: The content blocks.
            stop_reason: Why generation stopped.
        """
        self.content = blocks
        self.stop_reason = stop_reason


def anthropic_client_returning(
    response: object,
) -> tuple[AnthropicClient, FakeMessages]:
    """Build a client whose transport is replaced by a canned response.

    Args:
        response: The response or exception the fake should produce.

    Returns:
        The client and the fake, so the request it built can be inspected.
    """
    client = AnthropicClient(settings_for(LLMProvider.ANTHROPIC))
    messages = FakeMessages(response)
    client._client = type("Fake", (), {"messages": messages})()
    return client, messages


def test_each_provider_gets_the_right_client() -> None:
    """Claude has its own client; everything else shares the OpenAI-compatible one."""
    assert isinstance(
        AnthropicClient(settings_for(LLMProvider.ANTHROPIC)), AnthropicClient
    )
    assert isinstance(
        OpenAICompatibleClient(
            settings_for(LLMProvider.OLLAMA, llm_api_key=SecretStr(""))
        ),
        OpenAICompatibleClient,
    )


def test_anthropic_defaults_to_a_current_model() -> None:
    """A stale default model ID is a 404 at request time, not at start-up."""
    assert settings_for(LLMProvider.ANTHROPIC).resolved_llm_model.startswith("claude-")


async def test_text_blocks_are_joined() -> None:
    """A response can arrive as several text blocks; the caller wants one document."""
    client, _ = anthropic_client_returning(
        Response([Block('{"suggestions":'), Block(" []}")])
    )

    assert await client.complete_json(system="s", user="u") == '{"suggestions": []}'


async def test_sampling_parameters_are_never_sent() -> None:
    """Current Claude models reject temperature, top_p and top_k with a 400.

    Passing them through from a shared LLM config would fail the request outright
    rather than degrade, so this pins their absence.
    """
    client, messages = anthropic_client_returning(Response([Block("{}")]))

    await client.complete_json(system="s", user="u")

    for forbidden in ("temperature", "top_p", "top_k"):
        assert forbidden not in messages.kwargs


async def test_a_refusal_is_an_error_not_an_empty_answer() -> None:
    """A declined request is HTTP 200 with no usable content.

    Reading `content[0]` without checking `stop_reason` raises IndexError on what is a
    normal outcome — and retrying a refusal only burns tokens on the same answer.
    """
    client, _ = anthropic_client_returning(Response([], stop_reason="refusal"))

    with pytest.raises(LLMError):
        await client.complete_json(system="s", user="u")


async def test_a_transport_failure_becomes_an_llm_error() -> None:
    """Callers handle one error type; the provider's own class does not leak out."""
    client, _ = anthropic_client_returning(
        anthropic.APIConnectionError(request=None)  # type: ignore[arg-type]
    )

    with pytest.raises(LLMError):
        await client.complete_json(system="s", user="u")


def test_a_hosted_provider_is_refused_in_local_only_mode() -> None:
    """`local_only` is a hard switch that fails closed, and Claude is hosted."""
    with pytest.raises(ValueError, match="local"):
        settings_for(LLMProvider.ANTHROPIC, local_only=True)


def test_local_only_refuses_a_remote_ollama_url() -> None:
    """The provider name is not the guarantee — the destination is.

    Ollama speaks the OpenAI wire format, so a hosted endpoint behind
    `provider=ollama` would satisfy the provider check and still send the user's CV
    off the machine.
    """
    with pytest.raises(ValueError, match="local_only"):
        settings_for(
            LLMProvider.OLLAMA,
            llm_api_key=SecretStr(""),
            llm_base_url="https://api.example.com/v1",
            local_only=True,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://host.docker.internal:11434/v1",  # the container reaching its host
        "http://ollama:11434/v1",  # the compose service name
        "http://192.168.1.20:11434/v1",  # a model on the LAN
    ],
)
def test_local_only_allows_local_destinations(base_url: str) -> None:
    """Every way a local model is actually reached has to keep working."""
    settings = settings_for(
        LLMProvider.OLLAMA,
        llm_api_key=SecretStr(""),
        llm_base_url=base_url,
        local_only=True,
    )

    assert settings.resolved_llm_base_url == base_url


def test_anthropic_requires_an_api_key() -> None:
    """Failing at start-up beats failing on the first analysis a user runs."""
    with pytest.raises(ValueError, match="key"):
        settings_for(LLMProvider.ANTHROPIC, llm_api_key=SecretStr(""))
