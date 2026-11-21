"""Tests for provider presets and model configuration."""

import textwrap

import pytest
import yaml

from tetris_bench.clients.config import (
    ModelConfig,
    Pricing,
    load_model_config,
    load_model_configs,
    parse_model_configs,
)
from tetris_bench.clients.providers import (
    LOCAL_PLACEHOLDER_KEY,
    PROVIDER_NAMES,
    get_provider,
)


class TestProviders:
    @pytest.mark.parametrize("name", PROVIDER_NAMES)
    def test_every_provider_resolves(self, name):
        assert get_provider(name).name == name

    def test_local_providers_need_no_key(self):
        assert not get_provider("ollama").requires_key
        assert not get_provider("lmstudio").requires_key

    def test_cloud_providers_need_a_key(self):
        assert get_provider("openai").requires_key
        assert get_provider("anthropic").requires_key

    def test_local_providers_point_at_localhost(self):
        for name in ("ollama", "lmstudio"):
            assert "localhost" in get_provider(name).base_url

    def test_openai_uses_the_sdk_default_base_url(self):
        assert get_provider("openai").base_url is None

    def test_unknown_provider_lists_the_valid_ones(self):
        with pytest.raises(ValueError, match="unknown provider 'nope'"):
            get_provider("nope")
        with pytest.raises(ValueError, match="ollama"):
            get_provider("nope")


class TestPricing:
    def test_zero_by_default(self):
        assert Pricing().cost(1000, 1000) == 0.0

    def test_costs_per_million_tokens(self):
        pricing = Pricing(input_per_million=15.0, output_per_million=75.0)
        assert pricing.cost(1_000_000, 0) == 15.0
        assert pricing.cost(0, 1_000_000) == 75.0

    def test_scales_down(self):
        pricing = Pricing(input_per_million=10.0, output_per_million=0.0)
        assert pricing.cost(1000, 0) == pytest.approx(0.01)

    def test_combines_input_and_output(self):
        pricing = Pricing(input_per_million=1.0, output_per_million=2.0)
        assert pricing.cost(1_000_000, 1_000_000) == pytest.approx(3.0)


class TestProviderSpec:
    def test_inherits_the_preset(self):
        config = ModelConfig(name="local", provider="ollama", model="qwen3")
        spec = config.provider_spec
        assert spec.base_url == "http://localhost:11434/v1"
        assert spec.api_key_env is None

    def test_base_url_can_be_overridden(self):
        config = ModelConfig(
            name="remote", provider="ollama", model="qwen3", base_url="http://box:11434/v1"
        )
        assert config.provider_spec.base_url == "http://box:11434/v1"

    def test_api_key_env_can_be_overridden(self):
        config = ModelConfig(
            name="gw", provider="openai", model="gpt", api_key_env="MY_GATEWAY_KEY"
        )
        assert config.provider_spec.api_key_env == "MY_GATEWAY_KEY"


class TestParse:
    def parse(self, text: str):
        return parse_model_configs(yaml.safe_load(textwrap.dedent(text)), source="t.yaml")

    def test_minimal_entry(self):
        (config,) = self.parse(
            """
            models:
              - name: local
                provider: ollama
                model: qwen3:30b
            """
        )
        assert config.name == "local"
        assert config.model == "qwen3:30b"
        assert config.pricing == Pricing()
        assert config.temperature == 0.0
        assert config.max_retries == 3

    def test_temperature_defaults_to_zero_for_reproducibility(self):
        (config,) = self.parse("models:\n  - {name: a, provider: ollama, model: m}\n")
        assert config.temperature == 0.0

    def test_frequency_penalty_defaults_to_none(self):
        """Off unless a rung asks for it, so no rung's sampling changes silently."""
        (config,) = self.parse("models:\n  - {name: a, provider: ollama, model: m}\n")
        assert config.frequency_penalty is None

    def test_frequency_penalty_is_read(self):
        (config,) = self.parse(
            "models:\n  - {name: a, provider: ollama, model: m, frequency_penalty: 0.5}\n"
        )
        assert config.frequency_penalty == 0.5

    def test_full_entry(self):
        (config,) = self.parse(
            """
            models:
              - name: opus
                provider: anthropic
                model: claude-opus-4
                pricing:
                  input_per_million: 15.0
                  output_per_million: 75.0
                temperature: 0.5
                max_tokens: 2048
                timeout_seconds: 60
                max_retries: 5
            """
        )
        assert config.pricing.output_per_million == 75.0
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 60
        assert config.max_retries == 5

    def test_rejects_a_missing_models_key(self):
        with pytest.raises(ValueError, match="top-level 'models' key"):
            parse_model_configs({"foo": 1}, source="t.yaml")

    def test_rejects_an_empty_models_list(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_model_configs({"models": []}, source="t.yaml")

    @pytest.mark.parametrize("missing", ["name", "provider", "model"])
    def test_rejects_a_missing_required_key(self, missing):
        entry = {"name": "a", "provider": "ollama", "model": "m"}
        del entry[missing]
        with pytest.raises(ValueError, match=f"missing required key '{missing}'"):
            parse_model_configs({"models": [entry]}, source="t.yaml")

    def test_rejects_an_unknown_key_rather_than_ignoring_it(self):
        """A typo in a config must not silently do nothing."""
        with pytest.raises(ValueError, match="unknown keys"):
            parse_model_configs(
                {"models": [{"name": "a", "provider": "ollama", "model": "m", "temprature": 1}]},
                source="t.yaml",
            )

    def test_rejects_an_unknown_provider_at_load_time(self):
        """Fails on load, not halfway through an expensive run."""
        with pytest.raises(ValueError, match="unknown provider"):
            parse_model_configs(
                {"models": [{"name": "a", "provider": "groq", "model": "m"}]}, source="t.yaml"
            )

    def test_rejects_unknown_pricing_keys(self):
        with pytest.raises(ValueError, match="pricing has unknown keys"):
            parse_model_configs(
                {
                    "models": [
                        {"name": "a", "provider": "ollama", "model": "m", "pricing": {"input": 1}}
                    ]
                },
                source="t.yaml",
            )

    def test_rejects_duplicate_names(self):
        with pytest.raises(ValueError, match="duplicate model names"):
            parse_model_configs(
                {
                    "models": [
                        {"name": "a", "provider": "ollama", "model": "m"},
                        {"name": "a", "provider": "ollama", "model": "n"},
                    ]
                },
                source="t.yaml",
            )

    def test_error_names_the_offending_entry(self):
        with pytest.raises(ValueError, match=r"t\.yaml: models\[1\]"):
            parse_model_configs(
                {
                    "models": [
                        {"name": "a", "provider": "ollama", "model": "m"},
                        {"name": "b", "provider": "ollama"},
                    ]
                },
                source="t.yaml",
            )


class TestLoadFromDisk:
    def test_round_trips_a_file(self, tmp_path):
        path = tmp_path / "models.yaml"
        path.write_text("models:\n  - name: local\n    provider: ollama\n    model: qwen3\n")
        (config,) = load_model_configs(path)
        assert config.name == "local"

    def test_selects_one_by_name(self, tmp_path):
        path = tmp_path / "models.yaml"
        path.write_text(
            "models:\n"
            "  - {name: a, provider: ollama, model: m}\n"
            "  - {name: b, provider: lmstudio, model: n}\n"
        )
        assert load_model_config(path, "b").provider == "lmstudio"

    def test_missing_name_lists_what_is_available(self, tmp_path):
        path = tmp_path / "models.yaml"
        path.write_text("models:\n  - {name: a, provider: ollama, model: m}\n")
        with pytest.raises(ValueError, match="available: a"):
            load_model_config(path, "nope")


def test_the_projects_own_config_is_valid():
    """The committed configs/models.yaml must actually parse."""
    configs = load_model_configs("configs/models.yaml")
    assert len(configs) >= 2
    assert "qwen3-30b" in {config.name for config in configs}


def test_the_projects_config_is_local_only():
    """The project runs no paid models, so nothing live may need a key."""
    for config in load_model_configs("configs/models.yaml"):
        assert not config.provider_spec.requires_key, f"{config.name} needs an API key"
        assert config.pricing == Pricing(), f"{config.name} is local, so it should be free"


def test_the_config_is_a_size_ladder():
    """The ladder is the experiment: one family at increasing sizes."""
    configs = load_model_configs("configs/models.yaml")
    assert len(configs) >= 3, "a ladder needs several rungs to compare"
    assert len({config.model for config in configs}) == len(configs), "rungs must differ"


def test_local_placeholder_key_is_non_empty():
    """The SDK rejects an empty key even when the server ignores it."""
    assert LOCAL_PLACEHOLDER_KEY
