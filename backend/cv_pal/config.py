from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cv_pal.constants import (
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_ERROR_API_KEY_REQUIRED,
    DEFAULT_ERROR_BASE_URL_REQUIRED,
    DEFAULT_ERROR_LOCAL_ONLY_REMOTE_URL,
    DEFAULT_ERROR_LOCAL_ONLY_VIOLATION,
    DEFAULT_JWT_ALGORITHM,
    DEFAULT_LLM_BASE_URL_OLLAMA,
    DEFAULT_LLM_MODEL_OLLAMA,
    DEFAULT_LLM_MODEL_OPENAI,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
    DEFAULT_UPLOAD_DIR,
    LLMProvider,
)


def _is_local_host(host: str) -> bool:
    """Report whether a URL host is on this machine or this network.

    A name and address test rather than a DNS lookup: resolving at import time would
    make start-up depend on the network.

    Args:
        host: The hostname or IP literal taken from a URL.

    Returns:
        True when the host is a private/loopback address, a bare name with no domain
        (a container or LAN name such as ``ollama``), or one of the reserved local
        suffixes — ``host.docker.internal`` among them.
    """
    try:
        address = ip_address(host)
    except ValueError:
        return "." not in host or host.endswith((".local", ".internal", ".localhost"))
    return address.is_loopback or address.is_private or address.is_link_local


class Settings(BaseSettings):
    """Application settings loaded from environment variables with CV_PAL_ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="CV_PAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    secret_key: SecretStr
    database_url: str = "sqlite+aiosqlite:///./cv_pal.db"
    upload_dir: Path = DEFAULT_UPLOAD_DIR
    algorithm: str = DEFAULT_JWT_ALGORITHM
    access_token_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS
    cors_origins: list[str] = []

    allow_registration: bool = True

    # LLM
    llm_provider: LLMProvider = DEFAULT_LLM_PROVIDER
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS

    # When true, no request may leave the machine: only local providers are allowed.
    local_only: bool = False

    @property
    def resolved_llm_model(self) -> str:
        """Return the configured model, falling back to the provider default.

        Returns:
            The model name to use for completions.
        """
        if self.llm_model:
            return self.llm_model
        if self.llm_provider is LLMProvider.OLLAMA:
            return DEFAULT_LLM_MODEL_OLLAMA
        if self.llm_provider is LLMProvider.ANTHROPIC:
            return DEFAULT_ANTHROPIC_MODEL
        return DEFAULT_LLM_MODEL_OPENAI

    @property
    def resolved_llm_base_url(self) -> str | None:
        """Return the base URL for the configured provider.

        Returns:
            The base URL, or ``None`` to use the provider SDK default.
        """
        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider is LLMProvider.OLLAMA:
            return DEFAULT_LLM_BASE_URL_OLLAMA
        return None

    @model_validator(mode="after")
    def validate_llm_configuration(self) -> Self:
        """Ensure the selected LLM provider is fully and safely configured.

        Returns:
            The validated settings instance.

        Raises:
            ValueError: If the provider lacks a required credential or base URL, or if
                a hosted provider is selected while ``local_only`` is enabled.
        """
        if self.local_only and self.llm_provider is not LLMProvider.OLLAMA:
            raise ValueError(
                DEFAULT_ERROR_LOCAL_ONLY_VIOLATION.format(provider=self.llm_provider)
            )

        # The provider name is not the guarantee: Ollama speaks the OpenAI wire
        # format, so a hosted base URL passes the check above and still leaves.
        if self.local_only and self.llm_base_url:
            hostname = urlparse(self.llm_base_url).hostname
            if hostname is None or not _is_local_host(hostname):
                raise ValueError(
                    DEFAULT_ERROR_LOCAL_ONLY_REMOTE_URL.format(
                        base_url=self.llm_base_url
                    )
                )

        if (
            self.llm_provider in (LLMProvider.OPENAI, LLMProvider.ANTHROPIC)
            and not self.llm_api_key.get_secret_value()
        ):
            raise ValueError(
                DEFAULT_ERROR_API_KEY_REQUIRED.format(provider=self.llm_provider)
            )

        if self.llm_provider is LLMProvider.CUSTOM:
            if not self.llm_api_key.get_secret_value():
                raise ValueError(
                    DEFAULT_ERROR_API_KEY_REQUIRED.format(provider=self.llm_provider)
                )
            if not self.llm_base_url:
                raise ValueError(
                    DEFAULT_ERROR_BASE_URL_REQUIRED.format(provider=self.llm_provider)
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings.

    Returns:
        The process-wide ``Settings`` instance.
    """
    return Settings()  # type: ignore[call-arg]  # values come from the environment
