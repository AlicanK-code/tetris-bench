"""Tests for the model client: retries, usage tracking and cost.

No network, no API key and no running Ollama: the transport is injected. That
matters because the code that records failures has to be exercised on purpose
rather than when a provider happens to be down.
"""

import pytest

from tetris_bench.clients.client import ModelClient, resolve_api_key
from tetris_bench.clients.config import ModelConfig, Pricing
from tetris_bench.clients.providers import LOCAL_PLACEHOLDER_KEY
from tetris_bench.clients.transport import (
    PermanentModelError,
    RawCompletion,
    TransientModelError,
)

MESSAGES = [{"role": "user", "content": "hi"}]


class FakeTransport:
    """Returns queued results, raising any that are exceptions."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0) if self.results else RawCompletion("ok", "m", 1, 1)
        if isinstance(result, Exception):
            raise result
        return result


class TestSamplingConfigReachesTheTransport:
    """The config is useless if `complete` drops it on the floor."""

    def test_frequency_penalty_is_forwarded(self):
        config = ModelConfig(name="local", provider="ollama", model="m", frequency_penalty=0.5)
        client, transport = build_client(config=config)
        client.complete([{"role": "user", "content": "hi"}])
        assert transport.calls[0]["frequency_penalty"] == 0.5

    def test_none_is_forwarded_as_none(self):
        client, transport = build_client()
        client.complete([{"role": "user", "content": "hi"}])
        assert transport.calls[0]["frequency_penalty"] is None


class FakeClock:
    """Advances a fixed amount every time it is read."""

    def __init__(self, step=0.5):
        self.now = 0.0
        self.step = step

    def __call__(self):
        value = self.now
        self.now += self.step
        return value


def build_client(*results, config=None, sleeps=None):
    config = config or ModelConfig(name="local", provider="ollama", model="m")
    transport = FakeTransport(*results)
    client = ModelClient(
        config,
        transport=transport,
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
        clock=FakeClock(),
    )
    return client, transport


class TestResolveApiKey:
    def test_local_providers_get_a_placeholder(self):
        config = ModelConfig(name="local", provider="ollama", model="m")
        assert resolve_api_key(config, environ={}) == LOCAL_PLACEHOLDER_KEY

    def test_cloud_provider_reads_the_environment(self):
        config = ModelConfig(name="opus", provider="anthropic", model="m")
        assert resolve_api_key(config, environ={"ANTHROPIC_API_KEY": "sk-1"}) == "sk-1"

    def test_missing_key_fails_at_setup_not_mid_run(self):
        config = ModelConfig(name="opus", provider="anthropic", model="m")
        with pytest.raises(PermanentModelError, match="ANTHROPIC_API_KEY"):
            resolve_api_key(config, environ={})

    def test_empty_key_is_treated_as_missing(self):
        config = ModelConfig(name="opus", provider="anthropic", model="m")
        with pytest.raises(PermanentModelError):
            resolve_api_key(config, environ={"ANTHROPIC_API_KEY": ""})

    def test_overridden_env_var_is_honoured(self):
        config = ModelConfig(name="gw", provider="openai", model="m", api_key_env="MY_KEY")
        assert resolve_api_key(config, environ={"MY_KEY": "abc"}) == "abc"


class TestComplete:
    def test_returns_the_text_and_token_counts(self):
        client, _ = build_client(RawCompletion("hello", "qwen3", 120, 30))
        response = client.complete(MESSAGES)
        assert response.text == "hello"
        assert response.tokens_in == 120
        assert response.tokens_out == 30
        assert response.retries == 0

    def test_passes_the_config_through_to_the_transport(self):
        config = ModelConfig(
            name="a",
            provider="ollama",
            model="qwen3:30b",
            temperature=0.7,
            max_tokens=512,
            timeout_seconds=42.0,
        )
        client, transport = build_client(config=config)
        client.complete(MESSAGES)
        call = transport.calls[0]
        assert call["model"] == "qwen3:30b"
        assert call["temperature"] == 0.7
        assert call["max_tokens"] == 512
        assert call["timeout"] == 42.0
        assert call["messages"] == MESSAGES

    def test_measures_latency(self):
        client, _ = build_client(RawCompletion("x", "m", 1, 1))
        assert client.complete(MESSAGES).latency_seconds == pytest.approx(0.5)

    def test_falls_back_to_the_configured_model_name(self):
        """Some servers echo no model back."""
        client, _ = build_client(RawCompletion("x", "", 1, 1))
        assert client.complete(MESSAGES).model == "m"


class TestCost:
    def test_computed_from_the_configs_pricing(self):
        config = ModelConfig(
            name="opus",
            provider="ollama",
            model="m",
            pricing=Pricing(input_per_million=15.0, output_per_million=75.0),
        )
        client, _ = build_client(RawCompletion("x", "m", 1_000_000, 1_000_000), config=config)
        assert client.complete(MESSAGES).estimated_cost_usd == pytest.approx(90.0)

    def test_local_models_are_free(self):
        client, _ = build_client(RawCompletion("x", "m", 500_000, 500_000))
        assert client.complete(MESSAGES).estimated_cost_usd == 0.0


class TestRetries:
    def test_retries_a_transient_failure_and_succeeds(self):
        client, transport = build_client(
            TransientModelError("dropped"), RawCompletion("ok", "m", 1, 1)
        )
        response = client.complete(MESSAGES)
        assert response.text == "ok"
        assert response.retries == 1
        assert len(transport.calls) == 2

    def test_gives_up_after_max_retries(self):
        config = ModelConfig(name="a", provider="ollama", model="m", max_retries=2)
        client, transport = build_client(*[TransientModelError("nope")] * 3, config=config)
        with pytest.raises(TransientModelError, match="nope"):
            client.complete(MESSAGES)
        assert len(transport.calls) == 3  # one attempt plus two retries

    def test_max_retries_zero_means_a_single_attempt(self):
        config = ModelConfig(name="a", provider="ollama", model="m", max_retries=0)
        client, transport = build_client(TransientModelError("nope"), config=config)
        with pytest.raises(TransientModelError):
            client.complete(MESSAGES)
        assert len(transport.calls) == 1

    def test_does_not_retry_a_permanent_failure(self):
        """A bad key or missing model will not fix itself."""
        client, transport = build_client(PermanentModelError("bad key"))
        with pytest.raises(PermanentModelError):
            client.complete(MESSAGES)
        assert len(transport.calls) == 1

    def test_backs_off_exponentially(self):
        sleeps: list[float] = []
        config = ModelConfig(name="a", provider="ollama", model="m", max_retries=4)
        client, _ = build_client(
            *[TransientModelError("x")] * 4,
            RawCompletion("ok", "m", 1, 1),
            config=config,
            sleeps=sleeps,
        )
        client.complete(MESSAGES)
        assert sleeps == [1.0, 2.0, 4.0, 8.0]

    def test_backoff_is_capped(self):
        sleeps: list[float] = []
        config = ModelConfig(name="a", provider="ollama", model="m", max_retries=8)
        client, _ = build_client(
            *[TransientModelError("x")] * 8,
            RawCompletion("ok", "m", 1, 1),
            config=config,
            sleeps=sleeps,
        )
        client.complete(MESSAGES)
        assert max(sleeps) == 30.0


class TestUsage:
    def test_starts_empty(self):
        client, _ = build_client()
        assert client.usage.model_calls == 0
        assert client.usage.tokens_in == 0

    def test_accumulates_across_calls(self):
        client, _ = build_client(RawCompletion("a", "m", 100, 10), RawCompletion("b", "m", 200, 20))
        client.complete(MESSAGES)
        client.complete(MESSAGES)
        assert client.usage.model_calls == 2
        assert client.usage.tokens_in == 300
        assert client.usage.tokens_out == 30

    def test_counts_logical_calls_not_attempts(self):
        """One call that needed two attempts is still one call, plus one retry."""
        client, _ = build_client(TransientModelError("x"), RawCompletion("ok", "m", 5, 5))
        client.complete(MESSAGES)
        assert client.usage.model_calls == 1
        assert client.usage.retries == 1

    def test_records_a_failed_call(self):
        """A run's cost includes the calls that did not work."""
        client, _ = build_client(PermanentModelError("bad"))
        with pytest.raises(PermanentModelError):
            client.complete(MESSAGES)
        assert client.usage.model_calls == 1
        assert client.usage.failed_calls == 1

    def test_failed_call_still_records_latency(self):
        client, _ = build_client(PermanentModelError("bad"))
        with pytest.raises(PermanentModelError):
            client.complete(MESSAGES)
        assert client.usage.latency_seconds > 0

    def test_exhausted_retries_count_as_one_failed_call(self):
        config = ModelConfig(name="a", provider="ollama", model="m", max_retries=2)
        client, _ = build_client(*[TransientModelError("x")] * 3, config=config)
        with pytest.raises(TransientModelError):
            client.complete(MESSAGES)
        assert client.usage.model_calls == 1
        assert client.usage.failed_calls == 1
        assert client.usage.retries == 2

    def test_accumulates_cost(self):
        config = ModelConfig(
            name="a",
            provider="ollama",
            model="m",
            pricing=Pricing(input_per_million=10.0, output_per_million=0.0),
        )
        client, _ = build_client(
            RawCompletion("a", "m", 1_000_000, 0),
            RawCompletion("b", "m", 1_000_000, 0),
            config=config,
        )
        client.complete(MESSAGES)
        client.complete(MESSAGES)
        assert client.usage.estimated_cost_usd == pytest.approx(20.0)

    def test_reset_clears_the_tally(self):
        """So one game's usage can be recorded on its own."""
        client, _ = build_client(RawCompletion("a", "m", 10, 10))
        client.complete(MESSAGES)
        client.reset_usage()
        assert client.usage.model_calls == 0
        assert client.usage.tokens_in == 0

    def test_usage_is_a_frozen_snapshot(self):
        client, _ = build_client(RawCompletion("a", "m", 10, 10))
        before = client.usage
        client.complete(MESSAGES)
        assert before.model_calls == 0
        assert client.usage.model_calls == 1


class TestSeedOverride:
    """Sampling generation noise means varying the seed per call, not per client."""

    def test_the_override_reaches_the_transport(self):
        config = ModelConfig(name="local", provider="ollama", model="m", seed=1)
        client, transport = build_client(config=config)
        client.complete([{"role": "user", "content": "hi"}], seed=9)
        assert transport.calls[0]["seed"] == 9

    def test_without_an_override_the_configured_seed_is_used(self):
        config = ModelConfig(name="local", provider="ollama", model="m", seed=1)
        client, transport = build_client(config=config)
        client.complete([{"role": "user", "content": "hi"}])
        assert transport.calls[0]["seed"] == 1

    def test_seed_zero_is_an_override_not_a_default(self):
        """0 is falsy; `if seed` instead of `if seed is None` would silently drop it."""
        config = ModelConfig(name="local", provider="ollama", model="m", seed=1)
        client, transport = build_client(config=config)
        client.complete([{"role": "user", "content": "hi"}], seed=0)
        assert transport.calls[0]["seed"] == 0
