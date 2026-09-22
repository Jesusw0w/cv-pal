import logging
from functools import cache
from typing import Protocol

import anthropic
import openai
import pydantic

from cv_pal.config import Settings, get_settings
from cv_pal.constants import (
    DEFAULT_ANTHROPIC_MAX_TOKENS,
    DEFAULT_LLM_API_KEY_PLACEHOLDER,
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_MODEL_MISSING,
    DEFAULT_LLM_PROBE_TIMEOUT_SECONDS,
    DEFAULT_LLM_UNREACHABLE,
    LLMProvider,
)
from cv_pal.exceptions import LLMError, LLMResponseError

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """A minimal, provider-agnostic language model interface.

    Implementations must be safe to call concurrently and must never block the event
    loop. Tests substitute a fake implementation rather than calling a real model.
    """

    @property
    def model(self) -> str:
        """Return the model identifier used for completions."""
        ...

    async def complete_json(self, *, system: str, user: str) -> str:
        """Request a JSON response from the model.

        Args:
            system: The system prompt describing the task and output shape.
            user: The user prompt carrying the content to process.

        Returns:
            The raw response text, expected to contain a JSON document.

        Raises:
            LLMError: If the provider is unreachable or returns no content.
        """
        ...

    async def check(self) -> str | None:
        """Probe whether the configured model can be used.

        Returns:
            None when the model is available, otherwise what is wrong, phrased for a
            person reading it.
        """
        ...


async def complete_validated[T: pydantic.BaseModel](
    client: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[T],
    retry_prompt: str,
) -> T:
    """Ask the model for JSON and validate it, with one corrective retry.

    Local models ignore an output schema often enough that one retry pays for itself,
    and rarely enough that a second does not. Anything still invalid is rejected —
    every caller of this feeds a database or a document.

    Args:
        client: The language model client.
        system: The system prompt.
        user: The user prompt.
        schema: The model the response must validate against.
        retry_prompt: A template taking `error`, appended to the user prompt on retry.

    Returns:
        The validated response.

    Raises:
        LLMResponseError: If the output fails validation twice.
        LLMError: If the provider is unreachable.
    """
    raw = await client.complete_json(system=system, user=user)
    try:
        return schema.model_validate_json(raw)
    except pydantic.ValidationError as first_error:
        logger.info("LLM returned unparsable output, retrying once: %s", first_error)
        retry_user = f"{user}\n\n{retry_prompt.format(error=first_error)}"
        raw = await client.complete_json(system=system, user=retry_user)
        try:
            return schema.model_validate_json(raw)
        except pydantic.ValidationError as second_error:
            logger.warning("LLM output failed validation twice: %s", second_error)
            raise LLMResponseError from second_error


class OpenAICompatibleClient:
    """LLM client for any OpenAI-compatible chat completions endpoint.

    This covers hosted OpenAI, a local Ollama server, and self-hosted gateways such as
    vLLM, LM Studio or OpenRouter — they all speak the same wire protocol, so the only
    difference is the base URL and credentials.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the client from application settings.

        Args:
            settings: Resolved application settings selecting the provider.
        """
        self._model = settings.resolved_llm_model
        api_key = settings.llm_api_key.get_secret_value()
        if settings.llm_provider is LLMProvider.OLLAMA and not api_key:
            # Ollama ignores the credential but the SDK requires a non-empty value.
            api_key = DEFAULT_LLM_API_KEY_PLACEHOLDER
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=settings.resolved_llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=DEFAULT_LLM_MAX_RETRIES,
        )

    @property
    def model(self) -> str:
        """Return the model identifier used for completions.

        Returns:
            The resolved model name.
        """
        return self._model

    async def complete_json(self, *, system: str, user: str) -> str:
        """Request a JSON response from the configured model.

        Args:
            system: The system prompt describing the task and output shape.
            user: The user prompt carrying the content to process.

        Returns:
            The raw response text.

        Raises:
            LLMError: If the provider is unreachable or returns no content.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
        except openai.OpenAIError as exc:
            logger.warning("LLM request failed for model %s: %s", self._model, exc)
            raise LLMError from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError
        return content

    async def check(self) -> str | None:
        """Probe whether the configured model is installed or offered.

        Ollama lists local models with their tag, so ``llama3`` is also found as
        ``llama3:latest``.

        Returns:
            None when the model is listed, otherwise the problem.
        """
        probe = self._client.with_options(
            timeout=DEFAULT_LLM_PROBE_TIMEOUT_SECONDS, max_retries=0
        )
        try:
            ids = {model.id async for model in probe.models.list()}
        except openai.OpenAIError as exc:
            logger.warning("LLM availability probe failed: %s", exc)
            return DEFAULT_LLM_UNREACHABLE
        if self._model in ids or f"{self._model}:latest" in ids:
            return None
        return DEFAULT_LLM_MODEL_MISSING.format(model=self._model)


class AnthropicClient:
    """LLM client for Claude, through Anthropic's own SDK.

    Claude does not speak the OpenAI wire protocol, and reaching it through a
    compatibility gateway would give up the two things this codebase depends on:
    structured output, and the ``refusal`` stop reason that distinguishes "the model
    declined" from "the model produced garbage". `review_service` retries once on
    unparsable output, and retrying a refusal would just burn tokens on the same answer.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the client from application settings.

        Args:
            settings: Resolved application settings selecting the provider.
        """
        self._model = settings.resolved_llm_model
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=DEFAULT_LLM_MAX_RETRIES,
        )

    @property
    def model(self) -> str:
        """Return the model identifier used for completions.

        Returns:
            The resolved model name.
        """
        return self._model

    async def complete_json(self, *, system: str, user: str) -> str:
        """Request a JSON response from the configured model.

        The prompts already demand JSON and the caller validates the result, so no
        schema is passed here. Native structured output (``output_config.format``) would
        be stronger, but it needs the schema at this boundary — a change to the
        `LLMClient` Protocol, and therefore to every implementation.

        Note the parameters deliberately *absent*: current Claude models reject
        ``temperature``, ``top_p`` and ``top_k`` outright, so passing them through
        from a shared config would 400 rather than degrade.

        Args:
            system: The system prompt describing the task and output shape.
            user: The user prompt carrying the content to process.

        Returns:
            The raw response text.

        Raises:
            LLMError: If the provider is unreachable, declines the request, or returns
                no usable text.
        """
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=DEFAULT_ANTHROPIC_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as exc:
            logger.warning("Claude request failed for model %s: %s", self._model, exc)
            raise LLMError from exc

        # A declined request is a successful HTTP 200 with an empty or partial body, so
        # reading content[0] unchecked raises IndexError on a normal outcome.
        if response.stop_reason == "refusal":
            logger.warning("Claude declined the request for model %s", self._model)
            raise LLMError

        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise LLMError
        return text

    async def check(self) -> str | None:
        """Probe whether the configured model exists for this key.

        Returns:
            None when the model is available, otherwise the problem.
        """
        probe = self._client.with_options(
            timeout=DEFAULT_LLM_PROBE_TIMEOUT_SECONDS, max_retries=0
        )
        try:
            await probe.models.retrieve(self._model)
        except anthropic.NotFoundError:
            return DEFAULT_LLM_MODEL_MISSING.format(model=self._model)
        except anthropic.AnthropicError as exc:
            logger.warning("Claude availability probe failed: %s", exc)
            return DEFAULT_LLM_UNREACHABLE
        return None


@cache
def get_llm_client() -> LLMClient:
    """Provide the configured LLM client.

    Used as a FastAPI dependency so tests can override it with a fake. Cached, so one
    connection pool serves the process instead of a new, never-closed one per request.

    Returns:
        A client for the provider selected in settings. Anthropic has its own
        implementation; everything else speaks the OpenAI wire protocol and shares one.
    """
    settings = get_settings()
    if settings.llm_provider is LLMProvider.ANTHROPIC:
        return AnthropicClient(settings)
    return OpenAICompatibleClient(settings)
