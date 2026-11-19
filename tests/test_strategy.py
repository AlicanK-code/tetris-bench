"""Tests for the strategy agent, prompt rendering and code extraction.

No network and no local model: the client is faked, so the parse-and-play path
is exercised deterministically.
"""

import json
import re

import pytest

from tetris_bench.agents.strategy import (
    CODE_FENCE,
    GeneratedFunction,
    StrategyAgent,
    StrategyError,
    build_strategy_prompt,
    extract_code,
    request_scoring_function,
)
from tetris_bench.engine.game import Game
from tetris_bench.prompts import available, load, render
from tetris_bench.runner import play_game
from tetris_bench.sandbox import ScoringSandbox

EL_TETRIS = """
def score(board, placement):
    height = len(board)
    width = len(board[0])
    heights = [0] * width
    holes = 0
    for c in range(width):
        seen = False
        for r in range(height):
            if board[r][c]:
                if not seen:
                    heights[c] = height - r
                    seen = True
            elif seen:
                holes += 1
    bumpiness = 0
    for c in range(width - 1):
        bumpiness += abs(heights[c] - heights[c + 1])
    return (
        -0.510066 * sum(heights)
        + 0.760666 * placement["lines_cleared"]
        - 0.356630 * holes
        - 0.184483 * bumpiness
    )
"""


class FakeClient:
    """Returns a canned reply, recording what it was asked."""

    def __init__(self, text, reasoning=""):
        self.text = text
        self.reasoning = reasoning
        self.prompts = []

    def complete(self, messages):
        self.prompts.append(messages[-1]["content"])

        class Response:
            text = self.text
            reasoning = self.reasoning
            model = "fake-model"

        return Response()


class TestPrompts:
    def test_the_strategy_template_exists(self):
        assert "strategy_v1" in available()

    def test_version_is_in_the_filename(self):
        """An old run's prompt stays readable after a newer one exists."""
        assert all(re.search(r"_v\d+$", name) for name in available())

    def test_render_substitutes_every_placeholder(self):
        text = render("strategy_v1", width=10, height=20, last_row=19, per_call_seconds=1.0)
        assert not re.findall(r"\{[a-z_]+\}", text)

    def test_missing_value_raises_rather_than_leaking_a_brace(self):
        with pytest.raises(KeyError, match="height"):
            render("strategy_v1", width=10)

    def test_unknown_template_lists_what_exists(self):
        with pytest.raises(FileNotFoundError, match="strategy_v1"):
            load("nope")


class TestBuildStrategyPrompt:
    def test_states_the_board_dimensions(self):
        prompt = build_strategy_prompt(width=10, height=20)
        assert "20 rows" in prompt
        assert "10 booleans" in prompt

    def test_states_which_row_is_the_floor(self):
        """Row orientation is the single easiest thing to get wrong."""
        assert "row 19 is the floor" in build_strategy_prompt(height=20)

    def test_states_the_time_budget(self):
        assert "0.5 seconds" in build_strategy_prompt(per_call_seconds=0.5)

    def test_tells_the_model_math_needs_no_import(self):
        assert "already available" in build_strategy_prompt()

    def test_does_not_hand_over_the_feature_set(self):
        """Geometry only: discovering what matters is the thing being measured."""
        prompt = build_strategy_prompt().lower()
        assert "bumpiness" not in prompt
        assert "aggregate height" not in prompt


class TestExtractCode:
    def test_a_python_fenced_block(self):
        reply = "Here you go:\n```python\ndef score(board, placement):\n    return 1.0\n```\nDone."
        assert extract_code(reply).strip().startswith("def score")
        assert "Here you go" not in extract_code(reply)

    def test_a_bare_fence(self):
        assert "def score" in extract_code("```\ndef score(b, p):\n    return 1.0\n```")

    def test_a_py_language_tag(self):
        assert "def score" in extract_code("```py\ndef score(b, p):\n    return 1.0\n```")

    def test_the_first_block_wins(self):
        reply = "```python\ndef score(b, p):\n    return 1.0\n```\n```python\nirrelevant\n```"
        assert "irrelevant" not in extract_code(reply)

    def test_unfenced_code_falls_through_to_the_validator(self):
        """Better a clear validation error than a regex failure."""
        assert "def score" in extract_code("def score(b, p):\n    return 1.0\n")

    def test_always_ends_with_a_newline(self):
        assert extract_code("```python\ndef score(b, p):\n    return 1.0```").endswith("\n")

    def test_an_empty_reply_is_an_error(self):
        with pytest.raises(StrategyError, match="empty reply"):
            extract_code("")

    def test_a_whitespace_reply_is_an_error(self):
        with pytest.raises(StrategyError, match="empty reply"):
            extract_code("   \n  ")

    def test_an_empty_code_block_is_an_error(self):
        with pytest.raises(StrategyError, match="empty code block"):
            extract_code("```python\n\n```")

    def test_the_fence_pattern_is_case_insensitive(self):
        assert CODE_FENCE.search("```Python\nx\n```")


class TestRequestScoringFunction:
    def test_extracts_the_function_and_records_context(self):
        client = FakeClient("```python\ndef score(b, p):\n    return 1.0\n```", reasoning="hmm")
        generated = request_scoring_function(client, iteration=2)
        assert generated.source.startswith("def score")
        assert generated.model == "fake-model"
        assert generated.reasoning == "hmm"
        assert generated.iteration == 2
        assert "scoring candidate moves" in generated.prompt

    def test_keeps_the_raw_reply_for_debugging(self):
        client = FakeClient("prose\n```python\ndef score(b, p):\n    return 1.0\n```")
        assert "prose" in request_scoring_function(client).raw_reply

    def test_passes_the_time_budget_into_the_prompt(self):
        client = FakeClient("```python\ndef score(b, p):\n    return 1.0\n```")
        request_scoring_function(client, per_call_seconds=0.25)
        assert "0.25 seconds" in client.prompts[0]

    def test_an_unparseable_reply_raises(self):
        with pytest.raises(StrategyError):
            request_scoring_function(FakeClient(""))


class TestGeneratedFunctionSave:
    def build(self):
        return GeneratedFunction(
            source="def score(b, p):\n    return 1.0\n",
            model="qwen3:4b",
            prompt="the prompt",
            raw_reply="```python\n...\n```",
            reasoning="because",
            iteration=3,
        )

    def test_writes_runnable_source_separately(self, tmp_path):
        """The .py stays diffable on its own, for comparing iterations."""
        path = self.build().save(tmp_path, "run")
        assert path.name == "run.py"
        assert path.read_text().startswith("def score")

    def test_writes_the_context_as_json(self, tmp_path):
        self.build().save(tmp_path, "run")
        payload = json.loads((tmp_path / "run.json").read_text())
        assert payload["model"] == "qwen3:4b"
        assert payload["iteration"] == 3
        assert payload["reasoning"] == "because"
        assert payload["prompt"] == "the prompt"

    def test_creates_missing_directories(self, tmp_path):
        self.build().save(tmp_path / "deep" / "nested", "run")
        assert (tmp_path / "deep" / "nested" / "run.py").exists()

    def test_is_frozen(self):
        with pytest.raises(AttributeError):
            self.build().source = "x"


class TestStrategyAgent:
    def test_plays_a_full_game(self):
        with ScoringSandbox(EL_TETRIS) as sandbox:
            result = play_game(Game(seed=1, max_pieces=60), StrategyAgent(sandbox))
        assert result.pieces_placed == 60
        assert result.cause == "piece_limit"

    def test_is_named_for_logging(self):
        with ScoringSandbox(EL_TETRIS) as sandbox:
            assert StrategyAgent(sandbox).name == "strategy"

    def test_matches_the_native_heuristic_exactly(self):
        """The sandbox must add no distortion, or results are not comparable.

        Running the same weights in-process and through the sandbox has to give
        the identical game -- otherwise a model's score would partly measure the
        harness.
        """
        from tetris_bench.agents.heuristic import heuristic_agent

        native = play_game(Game(seed=1, max_pieces=200), heuristic_agent())
        with ScoringSandbox(EL_TETRIS) as sandbox:
            sandboxed = play_game(Game(seed=1, max_pieces=200), StrategyAgent(sandbox))
        assert sandboxed.score == native.score
        assert sandboxed.lines_cleared == native.lines_cleared

    def test_a_fully_broken_function_still_finishes_a_game(self):
        """It must record a result rather than abort the run.

        With every placement scoring negative infinity, `max` returns the first
        legal move, so the agent degenerates into "always rotation 0, column 0"
        and blocks out quickly with a score of zero. That is the intended
        fallback: a finished game with a recorded cause is more informative than
        an exception, and the signature is unmistakable in the logs.
        """
        source = "def score(board, placement):\n    raise ValueError('nope')\n"
        with ScoringSandbox(source, validate=False) as sandbox:
            result = play_game(Game(seed=1, max_pieces=30), StrategyAgent(sandbox))
            assert sandbox.failures > 0
        assert result.cause == "block_out"
        assert result.pieces_placed > 0
        assert result.score == 0

    def test_a_function_broken_on_some_boards_still_plays_well(self):
        """One bad branch costs moves, not the game."""
        source = EL_TETRIS.replace(
            "    bumpiness = 0",
            "    if placement['column'] == 3:\n        raise ValueError('bad branch')\n"
            "    bumpiness = 0",
        )
        with ScoringSandbox(source) as sandbox:
            result = play_game(Game(seed=1, max_pieces=100), StrategyAgent(sandbox))
            assert sandbox.failures > 0
        assert result.pieces_placed == 100
        assert result.score > 0

    def test_refuses_to_choose_when_the_game_is_over(self):
        game = Game(seed=1, max_pieces=1)
        game.step(game.legal_placements()[0])
        with ScoringSandbox(EL_TETRIS) as sandbox:
            agent = StrategyAgent(sandbox)
            game.board = type(game.board).from_strings(["X" * 10] * 20)
            with pytest.raises(ValueError, match="no legal placements"):
                agent.choose(game)


CONSTANT = "def score(board, placement):\n    return 1.0\n"

#: Reproduces the real failure: both terms are constant by construction, so the
#: function returns the same value for every candidate. See
#: docs/findings/qwen3-4b-iter0-detailed.md
LOOKS_REASONABLE_BUT_CONSTANT = """
def score(board, placement):
    stack_height = 0
    for row in range(20):
        if any(board[row][col] for col in range(10)):
            stack_height = row
    empty_cells = sum(1 for row in board for cell in row if not cell)
    return float(placement["lines_cleared"] * 10 + (100 - stack_height) + empty_cells * 0.1)
"""


class TestStrategyDiagnostics:
    def run(self, source, pieces=30, validate=True):
        with ScoringSandbox(source, validate=validate) as sandbox:
            agent = StrategyAgent(sandbox)
            result = play_game(Game(seed=1, max_pieces=pieces), agent)
            return agent.diagnostics, result, sandbox.failures

    def test_a_constant_function_is_flagged_degenerate(self):
        diagnostics, _, _ = self.run(CONSTANT)
        assert diagnostics.moves > 0
        assert diagnostics.flat_moves == diagnostics.moves
        assert diagnostics.mean_spread == 0.0
        assert diagnostics.is_degenerate

    def test_a_real_function_is_not_flagged(self):
        diagnostics, _, _ = self.run(EL_TETRIS, pieces=60)
        assert diagnostics.flat_moves == 0
        assert diagnostics.mean_spread > 0
        assert not diagnostics.is_degenerate

    def test_the_observed_failure_is_caught(self):
        """The function qwen3-4b actually wrote: valid, safe, and constant.

        It raises on nothing, so sandbox_failures is 0 and looks like success.
        Score spread is what exposes it.
        """
        diagnostics, result, failures = self.run(LOOKS_REASONABLE_BUT_CONSTANT)
        assert failures == 0
        assert diagnostics.is_degenerate
        assert result.score == 0

    def test_counts_unplayable_placements(self):
        source = "def score(board, placement):\n    raise ValueError('nope')\n"
        diagnostics, _, _ = self.run(source, pieces=10, validate=False)
        assert diagnostics.unplayable > 0

    def test_summary_names_the_problem(self):
        diagnostics, _, _ = self.run(CONSTANT, pieces=10)
        assert "effectively constant" in diagnostics.summary()

    def test_summary_is_quiet_when_the_function_works(self):
        diagnostics, _, _ = self.run(EL_TETRIS, pieces=20)
        assert "effectively constant" not in diagnostics.summary()
        assert "moves had score variation" in diagnostics.summary()

    def test_empty_diagnostics_do_not_divide_by_zero(self):
        from tetris_bench.agents.strategy import StrategyDiagnostics

        fresh = StrategyDiagnostics()
        assert fresh.mean_spread == 0.0
        assert fresh.flat_fraction == 0.0
        assert not fresh.is_degenerate
        assert fresh.summary() == "no moves scored"


class TestPromptVersions:
    def test_both_versions_are_available(self):
        """v1 stays on disk so an earlier run's prompt remains readable."""
        assert {"strategy_v1", "strategy_v2"} <= set(available())

    def test_the_default_is_the_newest_version(self):
        from tetris_bench.agents.strategy import DEFAULT_TEMPLATE

        assert DEFAULT_TEMPLATE == "strategy_v2"

    def test_v2_tells_the_model_its_scores_must_differ(self):
        """The fix for the observed failure: a constant function cannot choose."""
        prompt = build_strategy_prompt(template="strategy_v2")
        assert "must give different candidates different scores" in prompt
        assert "varies" in prompt

    def test_v2_clarifies_that_lines_cleared_is_not_in_the_board(self):
        """The trace showed the model concluding, wrongly, that it was."""
        prompt = build_strategy_prompt(template="strategy_v2")
        assert "not** recoverable from `board`" in prompt

    def test_v2_still_withholds_the_feature_set(self):
        """The clarifications must not leak strategy."""
        prompt = build_strategy_prompt(template="strategy_v2").lower()
        assert "bumpiness" not in prompt
        assert "aggregate height" not in prompt
        assert "covered" not in prompt

    def test_v1_is_unchanged_in_that_respect(self):
        prompt = build_strategy_prompt(template="strategy_v1")
        assert "must give different candidates different scores" not in prompt
