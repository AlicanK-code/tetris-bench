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
