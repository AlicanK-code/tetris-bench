"""Known providers and where to reach them.

Local runtimes serve on fixed localhost ports and need no credentials, and the
cloud providers' OpenAI-compatible endpoints are equally fixed. Keeping those
facts here rather than in YAML means a config entry says which provider and
which model, and nothing that would be identical in every config.

A config entry can still override ``base_url`` or ``api_key_env`` -- for a remote
Ollama box, or a gateway in front of a cloud provider.
"""

from __future__ import annotations

from dataclasses import dataclass

# The OpenAI SDK insists on a non-empty key even when the server ignores it, so
# local runtimes get a placeholder rather than a special code path.
LOCAL_PLACEHOLDER_KEY = "not-needed"


@dataclass(frozen=True)
class Provider:
    """Where a provider lives and how it authenticates."""

    name: str
    base_url: str | None
    api_key_env: str | None

    @property
    def requires_key(self) -> bool:
        """Whether a real credential is needed, as opposed to a placeholder."""
        return self.api_key_env is not None


PROVIDERS: dict[str, Provider] = {
    "ollama": Provider("ollama", "http://localhost:11434/v1", None),
    "lmstudio": Provider("lmstudio", "http://localhost:1234/v1", None),
    # base_url None means the SDK's own default.
    "openai": Provider("openai", None, "OPENAI_API_KEY"),
    "anthropic": Provider("anthropic", "https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY"),
}

PROVIDER_NAMES = tuple(PROVIDERS)


def get_provider(name: str) -> Provider:
    """Look up a provider, failing with the list of valid names."""
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"unknown provider {name!r}, expected one of {', '.join(PROVIDER_NAMES)}"
        ) from None
