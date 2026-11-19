"""Talking to models.

One OpenAI-compatible client serves local runtimes (Ollama, LM Studio) and cloud
providers alike; the provider is configuration, not code.
"""

from tetris_bench.clients.client import ChatResponse, ModelClient, resolve_api_key
from tetris_bench.clients.config import (
    ModelConfig,
    Pricing,
    load_model_config,
    load_model_configs,
    parse_model_configs,
)
from tetris_bench.clients.providers import PROVIDER_NAMES, PROVIDERS, Provider, get_provider
from tetris_bench.clients.transport import (
    ModelError,
    OpenAITransport,
    PermanentModelError,
    RawCompletion,
    TransientModelError,
    Transport,
)

__all__ = [
    "PROVIDERS",
    "PROVIDER_NAMES",
    "ChatResponse",
    "ModelClient",
    "ModelConfig",
    "ModelError",
    "OpenAITransport",
    "PermanentModelError",
    "Pricing",
    "Provider",
    "RawCompletion",
    "Transport",
    "TransientModelError",
    "get_provider",
    "load_model_config",
    "load_model_configs",
    "parse_model_configs",
    "resolve_api_key",
]
