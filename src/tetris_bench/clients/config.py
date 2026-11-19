"""Model configuration, loaded from YAML.

One entry describes one model well enough to call it and to price the call. The
pricing lives here rather than in a table in code because a run has to be
reproducible from its config and seed list: prices change, and a cost logged
months ago should still be explainable by the file that produced it. Local
models declare zero, which is a fact about them rather than a missing value.

```yaml
models:
  - name: qwen-local
    provider: ollama
    model: qwen3:30b
    pricing:
      input_per_million: 0
      output_per_million: 0
  - name: opus
    provider: anthropic
    model: claude-opus-4-20250514
    pricing:
      input_per_million: 15.0
      output_per_million: 75.0
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tetris_bench.clients.providers import Provider, get_provider

ALLOWED_KEYS = {
    "name",
    "provider",
    "model",
    "pricing",
    "base_url",
    "api_key_env",
    "temperature",
    "max_tokens",
    "timeout_seconds",
    "max_retries",
}


@dataclass(frozen=True)
class Pricing:
    """Dollars per million tokens, as declared by the config."""

    input_per_million: float = 0.0
    output_per_million: float = 0.0

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        """Estimated dollar cost of a call with these token counts."""
        return (
            tokens_in * self.input_per_million + tokens_out * self.output_per_million
        ) / 1_000_000


@dataclass(frozen=True)
class ModelConfig:
    """Everything needed to call one model and price the result."""

    name: str
    provider: str
    model: str
    pricing: Pricing = field(default_factory=Pricing)
    base_url: str | None = None
    api_key_env: str | None = None
    # Zero by default: a benchmark wants the same answer for the same prompt, and
    # sampling noise would show up as improvement that is not there.
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout_seconds: float = 120.0
    max_retries: int = 3

    @property
    def provider_spec(self) -> Provider:
        """The resolved provider, with any config overrides applied."""
        base = get_provider(self.provider)
        return Provider(
            name=base.name,
            base_url=self.base_url if self.base_url is not None else base.base_url,
            api_key_env=self.api_key_env if self.api_key_env is not None else base.api_key_env,
        )


def _parse_entry(entry: dict[str, Any], source: str, index: int) -> ModelConfig:
    """Turn one YAML mapping into a :class:`ModelConfig`, or explain why not."""
    where = f"{source}: models[{index}]"

    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be a mapping, got {type(entry).__name__}")

    unknown = set(entry) - ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"{where} has unknown keys {sorted(unknown)}; allowed: {sorted(ALLOWED_KEYS)}"
        )

    for required in ("name", "provider", "model"):
        if not entry.get(required):
            raise ValueError(f"{where} is missing required key {required!r}")

    # Validates the provider name early, so a typo fails at load rather than on
    # the first call halfway through a run.
    get_provider(entry["provider"])

    pricing_raw = entry.get("pricing") or {}
    if not isinstance(pricing_raw, dict):
        raise ValueError(f"{where}: pricing must be a mapping")
    unknown_pricing = set(pricing_raw) - {"input_per_million", "output_per_million"}
    if unknown_pricing:
        raise ValueError(f"{where}: pricing has unknown keys {sorted(unknown_pricing)}")

    return ModelConfig(
        name=entry["name"],
        provider=entry["provider"],
        model=entry["model"],
        pricing=Pricing(**pricing_raw),
        base_url=entry.get("base_url"),
        api_key_env=entry.get("api_key_env"),
        temperature=entry.get("temperature", 0.0),
        max_tokens=entry.get("max_tokens"),
        timeout_seconds=entry.get("timeout_seconds", 120.0),
        max_retries=entry.get("max_retries", 3),
    )


def parse_model_configs(data: Any, source: str = "<config>") -> list[ModelConfig]:
    """Parse an already-loaded config document."""
    if not isinstance(data, dict) or "models" not in data:
        raise ValueError(f"{source} must be a mapping with a top-level 'models' key")

    models = data["models"]
    if not isinstance(models, list) or not models:
        raise ValueError(f"{source}: 'models' must be a non-empty list")

    configs = [_parse_entry(entry, source, index) for index, entry in enumerate(models)]

    names = [config.name for config in configs]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"{source}: duplicate model names {duplicates}")

    return configs


def load_model_configs(path: Path | str) -> list[ModelConfig]:
    """Load every model entry from a YAML config file."""
    target = Path(path)
    with target.open(encoding="utf-8") as handle:
        return parse_model_configs(yaml.safe_load(handle), source=str(target))


def load_model_config(path: Path | str, name: str) -> ModelConfig:
    """Load the one entry called ``name``."""
    configs = load_model_configs(path)
    for config in configs:
        if config.name == name:
            return config
    available = ", ".join(sorted(config.name for config in configs))
    raise ValueError(f"no model named {name!r} in {path}; available: {available}")
