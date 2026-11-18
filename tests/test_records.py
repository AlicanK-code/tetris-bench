"""Tests for the logged record schema."""

import json

import pytest

from tetris_bench.metrics import BoardStats
from tetris_bench.records import GameResult, ModelUsage, RunRecord

SAMPLES = [
    BoardStats(aggregate_height=4, max_height=2, bumpiness=1, holes=0),
    BoardStats(aggregate_height=8, max_height=4, bumpiness=3, holes=2),
]
FINAL = BoardStats(aggregate_height=8, max_height=4, bumpiness=3, holes=2)


def build_result(**overrides) -> GameResult:
    defaults = dict(
        agent="heuristic",
        seed=1,
        agent_seed=None,
        score=800,
        lines_cleared=4,
        pieces_placed=2,
        cause="piece_limit",
        final=FINAL,
        samples=SAMPLES,
    )
    return GameResult.from_game_stats(**{**defaults, **overrides})


class TestGameResult:
    def test_copies_the_final_board_features(self):
        result = build_result()
        assert result.final_aggregate_height == 8
        assert result.final_max_height == 4
        assert result.final_bumpiness == 3
        assert result.final_holes == 2

    def test_averages_the_samples(self):
        result = build_result()
        assert result.avg_max_height == 3.0
        assert result.avg_bumpiness == 2.0
        assert result.avg_holes == 1.0

    def test_averages_are_zero_with_no_samples(self):
        """A game that ends before placing anything must not divide by zero."""
        result = build_result(samples=[])
        assert result.avg_max_height == 0.0
        assert result.avg_holes == 0.0

    def test_average_differs_from_final(self):
        """The point of sampling: a game can end tall having been played low."""
        result = build_result()
        assert result.avg_max_height != result.final_max_height

    def test_is_frozen(self):
        with pytest.raises(AttributeError):
            build_result().score = 0

    def test_as_dict_is_flat_and_json_safe(self):
        payload = build_result().as_dict()
        assert all(not isinstance(v, dict) for v in payload.values())
        assert json.loads(json.dumps(payload)) == payload

    def test_has_no_model_fields(self):
        """Baseline games produce a complete record with nothing left empty."""
        payload = build_result().as_dict()
        for model_field in ("model", "mode", "iteration", "tokens_in"):
            assert model_field not in payload
        assert all(value is not None for key, value in payload.items() if key != "agent_seed")


class TestModelUsage:
    def test_defaults_to_zero_not_none(self):
        """Zero calls is a fact; None would mean unknown."""
        usage = ModelUsage()
        assert usage.model_calls == 0
        assert usage.tokens_in == 0
        assert usage.estimated_cost_usd == 0.0
        assert usage.sandbox_failures == 0


class TestRunRecord:
    def test_wraps_a_game_result(self):
        record = RunRecord(game=build_result(), model="local/qwen", mode="strategy", iteration=3)
        assert record.game.score == 800
        assert record.iteration == 3

    def test_usage_defaults_to_an_empty_tally(self):
        record = RunRecord(game=build_result(), model="m", mode="strategy", iteration=0)
        assert record.usage == ModelUsage()

    def test_flattens_game_and_model_fields_into_one_level(self):
        record = RunRecord(
            game=build_result(),
            model="local/qwen",
            mode="strategy",
            iteration=3,
            usage=ModelUsage(model_calls=2, tokens_in=1500, tokens_out=400, latency_seconds=12.5),
        )
        payload = record.as_dict()
        assert payload["model"] == "local/qwen"
        assert payload["mode"] == "strategy"
        assert payload["iteration"] == 3
        assert payload["score"] == 800
        assert payload["tokens_in"] == 1500
        assert payload["latency_seconds"] == 12.5
        assert all(not isinstance(value, dict) for value in payload.values())

    def test_flattened_record_is_json_safe(self):
        record = RunRecord(game=build_result(), model="m", mode="direct", iteration=1)
        payload = record.as_dict()
        assert json.loads(json.dumps(payload)) == payload

    def test_covers_every_metric_the_project_logs(self):
        """Guards the schema against a field quietly going missing."""
        record = RunRecord(game=build_result(), model="m", mode="strategy", iteration=0)
        payload = record.as_dict()
        expected = {
            "model",
            "mode",
            "seed",
            "iteration",
            "score",
            "lines_cleared",
            "pieces_placed",
            "final_max_height",
            "avg_max_height",
            "final_holes",
            "final_bumpiness",
            "cause",
            "invalid_outputs",
            "sandbox_failures",
            "model_calls",
            "tokens_in",
            "tokens_out",
            "latency_seconds",
            "estimated_cost_usd",
        }
        assert expected <= set(payload)
