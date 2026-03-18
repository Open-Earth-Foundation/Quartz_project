from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI

import config
from .runtime import ensure_runtime_paths

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _sdk() -> Any:
    ensure_runtime_paths()
    import agents as openai_agents_sdk  # type: ignore

    return openai_agents_sdk


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    headers = {
        "HTTP-Referer": config.HTTP_REFERER,
        "X-Title": config.SITE_NAME,
    }
    return AsyncOpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        default_headers=headers,
    )


def configure_sdk() -> None:
    if not config.OPENROUTER_API_KEY or not config.ENABLE_SDK:
        return

    sdk = _sdk()
    sdk.set_default_openai_client(_client(), use_for_tracing=False)
    sdk.set_default_openai_api("chat_completions")
    if hasattr(sdk, "set_tracing_disabled"):
        sdk.set_tracing_disabled(True)


def sdk_available() -> bool:
    return bool(config.OPENROUTER_API_KEY and config.ENABLE_SDK)


def get_sdk() -> Any:
    configure_sdk()
    return _sdk()

