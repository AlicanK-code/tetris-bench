"""Tests for the command-line interface."""

import pytest

from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.cli import build_agent, build_parser, main


class TestBuildAgent:
    def test_builds_the_random_agent_with_its_seed(self):
        agent = build_agent("random", agent_seed=3)
        assert isinstance(agent, RandomAgent)
        assert agent.seed == 3

    def test_builds_the_heuristic_agent(self):
        assert build_agent("heuristic", agent_seed=0).name == "heuristic"

    def test_rejects_an_unknown_agent(self):
        with pytest.raises(ValueError, match="unknown agent"):
            build_agent("nope", agent_seed=0)


class TestParser:
    def test_defaults(self):
        args = build_parser().parse_args(["play"])
        assert args.agent == "heuristic"
        assert args.seed == 1

    def test_accepts_the_documented_invocation(self):
        args = build_parser().parse_args(["play", "--agent", "heuristic", "--seed", "1"])
        assert args.agent == "heuristic"
        assert args.seed == 1

    def test_rejects_an_unknown_agent(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["play", "--agent", "nope"])

    def test_requires_a_subcommand(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    @pytest.mark.parametrize("bad", ["0", "-1"])
    def test_rejects_a_meaningless_piece_budget_as_a_usage_error(self, bad, capsys):
        """A mistyped flag should give a usage message, not a traceback."""
        with pytest.raises(SystemExit):
            build_parser().parse_args(["play", "--max-pieces", bad])
        assert "at least 1" in capsys.readouterr().err

    def test_accepts_a_budget_of_one(self):
        assert build_parser().parse_args(["play", "--max-pieces", "1"]).max_pieces == 1


class TestMain:
    def test_play_prints_a_summary(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "sys.argv", ["tetris-bench", "play", "--seed", "1", "--max-pieces", "20"]
        )
        main()
        out = capsys.readouterr().out
        assert "heuristic" in out
        assert "score" in out
        assert "pieces placed  20" in out

    def test_quiet_prints_one_line(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["tetris-bench", "play", "--max-pieces", "10", "--quiet"],
        )
        main()
        out = capsys.readouterr().out.strip()
        assert out.count("\n") == 0
        assert out.startswith("heuristic")

    def test_show_state_prints_the_model_facing_view(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["tetris-bench", "play", "--max-pieces", "10", "--show-state"],
        )
        main()
        out = capsys.readouterr().out
        assert "0123456789" in out
        assert "current piece" in out
        assert "hold" not in out.lower()

    def test_log_appends_a_jsonl_record(self, capsys, monkeypatch, tmp_path):
        from tetris_bench.jsonl import read_records

        path = tmp_path / "runs" / "baseline.jsonl"
        monkeypatch.setattr(
            "sys.argv",
            ["tetris-bench", "play", "--max-pieces", "10", "--quiet", "--log", str(path)],
        )
        main()
        records = list(read_records(path))
        assert len(records) == 1
        assert records[0]["agent"] == "heuristic"
        assert records[0]["pieces_placed"] == 10

    def test_log_accumulates_across_runs(self, capsys, monkeypatch, tmp_path):
        from tetris_bench.jsonl import read_records

        path = tmp_path / "baseline.jsonl"
        for seed in (1, 2):
            monkeypatch.setattr(
                "sys.argv",
                [
                    "tetris-bench",
                    "play",
                    "--seed",
                    str(seed),
                    "--max-pieces",
                    "10",
                    "--quiet",
                    "--log",
                    str(path),
                ],
            )
            main()
        assert [r["seed"] for r in read_records(path)] == [1, 2]

    def test_random_agent_reports_its_seed(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "tetris-bench",
                "play",
                "--agent",
                "random",
                "--agent-seed",
                "5",
                "--max-pieces",
                "10",
                "--quiet",
            ],
        )
        main()
        assert "random" in capsys.readouterr().out


class TestHelpText:
    def test_description_is_a_single_readable_line(self):
        """argparse reflows its description, so __doc__ must not be used."""
        parser = build_parser()
        assert parser.description is not None
        assert "\n" not in parser.description
        assert "uv run" not in parser.description

    def test_examples_keep_their_line_breaks(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])
        out = capsys.readouterr().out
        assert "examples:" in out
        assert "tetris-bench play --agent heuristic --seed 1\n" in out


class TestModelsCommand:
    def test_lists_configured_models(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.argv", ["tetris-bench", "models"])
        main()
        out = capsys.readouterr().out
        assert "qwen3-30b" in out
        assert "ollama" in out
        assert "not needed" in out

    def test_reports_a_missing_cloud_key(self, monkeypatch):
        from tetris_bench.cli import format_models
        from tetris_bench.clients.config import ModelConfig

        configs = [ModelConfig(name="opus", provider="anthropic", model="m")]
        assert "ANTHROPIC_API_KEY MISSING" in format_models(configs, environ={})

    def test_reports_a_present_cloud_key_without_leaking_it(self):
        from tetris_bench.cli import format_models
        from tetris_bench.clients.config import ModelConfig

        configs = [ModelConfig(name="opus", provider="anthropic", model="m")]
        out = format_models(configs, environ={"ANTHROPIC_API_KEY": "sk-secret"})
        assert "ANTHROPIC_API_KEY set" in out
        assert "sk-secret" not in out

    def test_local_models_need_no_key(self):
        from tetris_bench.cli import format_models
        from tetris_bench.clients.config import ModelConfig

        configs = [ModelConfig(name="local", provider="ollama", model="m")]
        assert "not needed" in format_models(configs, environ={})

    def test_shows_pricing(self):
        from tetris_bench.cli import format_models
        from tetris_bench.clients.config import ModelConfig, Pricing

        configs = [
            ModelConfig(
                name="opus",
                provider="anthropic",
                model="m",
                pricing=Pricing(input_per_million=15.0, output_per_million=75.0),
            )
        ]
        out = format_models(configs, environ={})
        assert "15" in out
        assert "75" in out

    def test_rejects_a_missing_config_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sys.argv", ["tetris-bench", "models", "--config", str(tmp_path / "nope.yaml")]
        )
        with pytest.raises(FileNotFoundError):
            main()
