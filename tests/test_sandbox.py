"""Tests for the sandbox that runs model-written scoring functions.

The two layers are tested separately, but note what each set actually
establishes. :class:`TestValidateRefuses` covers the AST allowlist.
:class:`TestContainment` passes ``validate=False`` and covers what the *worker*
enforces by itself: that dangerous builtins are absent from its namespace, that
boards are immutable, that return values are checked, and that a call exceeding
its time budget is interrupted.

It does **not** show that the subprocess alone would contain everything the AST
check refuses. The worker does no attribute gating at all, so dunder-traversal
source is blocked by layer 1 only. The layers are complementary, not redundant,
and the honest description is the one in :mod:`tetris_bench.sandbox`: the static
check exists so a bad function fails instantly with a readable reason, not
because the subprocess could not otherwise limit the damage.
"""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.sandbox import (
    UNPLAYABLE,
    SandboxCrashed,
    SandboxLimits,
    SandboxValidationError,
    ScoringSandbox,
    build_items,
    validate_source,
)

TRIVIAL = "def score(board, placement):\n    return float(placement['lines_cleared'])\n"


@pytest.fixture
def items():
    game = Game(seed=1)
    return build_items(game.board, game.legal_placements())


class TestValidateAccepts:
    def test_a_trivial_function(self):
        validate_source(TRIVIAL)

    def test_helper_functions_above_score(self):
        validate_source(
            "def helper(rows):\n"
            "    return len(rows)\n"
            "def score(board, placement):\n"
            "    return float(helper(board))\n"
        )

    def test_math_without_importing_it(self):
        validate_source("def score(board, placement):\n    return math.sqrt(4.0)\n")

    def test_comprehensions_and_loops(self):
        validate_source(
            "def score(board, placement):\n"
            "    total = sum(1 for row in board if any(row))\n"
            "    for _ in range(3):\n"
            "        total += 1\n"
            "    return float(total)\n"
        )

    def test_positional_only_arguments_count(self):
        validate_source("def score(board, placement, /):\n    return 0.0\n")


class TestValidateRefuses:
    @pytest.mark.parametrize(
        ("label", "source"),
        [
            ("import", "import os\ndef score(board, placement):\n    return 0.0\n"),
            (
                "from import",
                "from os import system\ndef score(board, placement):\n    return 0.0\n",
            ),
            ("dunder attribute", "def score(board, placement):\n    return len(().__class__)\n"),
            ("private attribute", "def score(board, placement):\n    return board._x\n"),
            ("dunder name", "def score(board, placement):\n    return __name__\n"),
            ("open", "def score(board, placement):\n    return len(open('/etc/passwd'))\n"),
            ("eval", "def score(board, placement):\n    return eval('1')\n"),
            ("exec", "def score(board, placement):\n    exec('x=1')\n    return 0.0\n"),
            ("globals", "def score(board, placement):\n    return len(globals())\n"),
            ("getattr", "def score(board, placement):\n    return getattr(board, 'x', 0)\n"),
            ("type", "def score(board, placement):\n    return len(str(type(board)))\n"),
            ("async def", "async def score(board, placement):\n    return 0.0\n"),
        ],
    )
    def test_dangerous_source(self, label, source):
        with pytest.raises(SandboxValidationError):
            validate_source(source)

    def test_missing_score_function(self):
        with pytest.raises(SandboxValidationError, match="no function called 'score'"):
            validate_source("def rank(board, placement):\n    return 0.0\n")

    def test_wrong_arity(self):
        with pytest.raises(SandboxValidationError, match="expected 2"):
            validate_source("def score(board):\n    return 0.0\n")

    def test_syntax_error_names_the_line(self):
        with pytest.raises(SandboxValidationError, match="syntax error on line"):
            validate_source("def score(board, placement) return 0.0\n")

    def test_every_problem_is_reported_at_once(self):
        """A model revising its function should get the whole story in one go."""
        source = "import os\nimport sys\ndef score(board):\n    return open('x')\n"
        with pytest.raises(SandboxValidationError) as caught:
            validate_source(source)
        message = str(caught.value)
        assert "os" in message
        assert "sys" in message
        assert "open" in message
        assert "expected 2" in message

    def test_import_error_mentions_math_is_already_available(self):
        with pytest.raises(SandboxValidationError, match="already available"):
            validate_source("import math\ndef score(board, placement):\n    return 0.0\n")


class TestBuildItems:
    def test_one_item_per_placement(self, items):
        game = Game(seed=1)
        assert len(items) == len(game.legal_placements())

    def test_board_is_plain_nested_bools(self, items):
        board = items[0]["board"]
        assert isinstance(board, list)
        assert all(isinstance(cell, bool) for row in board for cell in row)

    def test_board_is_the_state_after_the_move(self, items):
        """Scoring the current board would rate every candidate identically."""
        filled = sum(cell for row in items[0]["board"] for cell in row)
        assert filled == 4

    def test_placement_carries_lines_cleared(self):
        board = Board.from_strings(["." * 10] * 19 + ["." + "X" * 9])
        game = Game(seed=1)
        game.board = board
        game.current = "I"
        items = build_items(board, game.legal_placements())
        assert any(item["placement"]["lines_cleared"] == 1 for item in items)

    def test_placement_keys(self, items):
        placement = items[0]["placement"]
        assert set(placement) == {"kind", "rotation", "column", "row", "cells", "lines_cleared"}

    def test_no_project_objects_leak_into_the_payload(self, items):
        """Nothing of this project may cross into the sandbox."""
        import json

        # Round-tripping also catches a type that serialises lossily, which a
        # bare dumps() would let through.
        assert json.loads(json.dumps(items)) == items


class TestScoring:
    def test_scores_every_placement(self, items):
        with ScoringSandbox(TRIVIAL) as sandbox:
            scores = sandbox.score(items)
        assert len(scores) == len(items)
        assert all(isinstance(value, float) for value in scores)

    def test_scores_are_in_the_order_given(self, items):
        source = "def score(board, placement):\n    return float(placement['column'])\n"
        with ScoringSandbox(source) as sandbox:
            scores = sandbox.score(items)
        assert scores == [float(item["placement"]["column"]) for item in items]

    def test_empty_batch_needs_no_round_trip(self):
        with ScoringSandbox(TRIVIAL) as sandbox:
            assert sandbox.score([]) == []

    def test_math_is_available(self, items):
        source = "def score(board, placement):\n    return math.sqrt(16.0)\n"
        with ScoringSandbox(source) as sandbox:
            assert sandbox.score(items[:1]) == [4.0]

    def test_one_worker_serves_many_batches(self, items):
        """A game is ~500 batches; spawning per batch would dominate the runtime."""
        with ScoringSandbox(TRIVIAL) as sandbox:
            for _ in range(5):
                assert len(sandbox.score(items)) == len(items)


class TestContainment:
    """Layer 2 alone, with the AST allowlist deliberately skipped."""

    def run(self, source, items, limits=None):
        with ScoringSandbox(source, limits=limits, validate=False) as sandbox:
            return sandbox.score(items[:2]), sandbox.failures, list(sandbox.errors)

    def test_open_is_absent_from_the_namespace(self, items):
        source = "def score(board, placement):\n    return len(open('/etc/passwd').read())\n"
        scores, failures, errors = self.run(source, items)
        assert scores == [UNPLAYABLE, UNPLAYABLE]
        assert failures == 2
        assert "NameError" in errors[0]

    def test_dunder_import_is_absent(self, items):
        source = "def score(board, placement):\n    return __import__('os').getpid()\n"
        scores, _, errors = self.run(source, items)
        assert scores == [UNPLAYABLE, UNPLAYABLE]
        assert "NameError" in errors[0]

    def test_an_import_statement_fails_to_load(self):
        """With no __import__ in builtins, the import cannot resolve."""
        source = "import os\ndef score(board, placement):\n    return 0.0\n"
        with (
            pytest.raises(SandboxValidationError, match="ImportError"),
            ScoringSandbox(source, validate=False),
        ):
            pass

    def test_the_board_is_immutable(self, items):
        source = "def score(board, placement):\n    board[0] = 1\n    return 0.0\n"
        _, _, errors = self.run(source, items)
        assert "TypeError" in errors[0]

    def test_a_non_numeric_return_is_a_failure(self, items):
        source = "def score(board, placement):\n    return 'high'\n"
        scores, _, errors = self.run(source, items)
        assert scores == [UNPLAYABLE, UNPLAYABLE]
        assert "expected a number" in errors[0]

    def test_a_bool_return_is_a_failure(self, items):
        """True would silently compare as 1.0 and look like a real score."""
        source = "def score(board, placement):\n    return True\n"
        _, _, errors = self.run(source, items)
        assert "expected a number" in errors[0]

    def test_nan_is_a_failure(self, items):
        """NaN would make max() arbitrary."""
        source = "def score(board, placement):\n    return float('nan')\n"
        _, _, errors = self.run(source, items)
        assert "NaN" in errors[0]

    def test_an_infinite_loop_is_interrupted(self, items):
        source = "def score(board, placement):\n    while True:\n        pass\n"
        limits = SandboxLimits(per_call_seconds=0.2, per_batch_seconds=10.0)
        scores, failures, errors = self.run(source, items, limits=limits)
        assert scores == [UNPLAYABLE, UNPLAYABLE]
        assert failures == 2
        assert "Timeout" in errors[0]

    def test_a_print_does_not_corrupt_the_protocol(self, items):
        """Model stdout goes to stderr so the JSON channel stays clean."""
        source = "def score(board, placement):\n    print('noise')\n    return 1.0\n"
        scores, failures, _ = self.run(source, items)
        assert scores == [1.0, 1.0]
        assert failures == 0


class TestLifecycle:
    def test_load_failure_is_reported_and_the_worker_closed(self):
        source = "def score(board, placement):\n    return 0.0\nraise ValueError('boom')\n"
        with (
            pytest.raises(SandboxValidationError, match="boom"),
            ScoringSandbox(source, validate=False),
        ):
            pass

    def test_source_without_score_fails_to_load(self):
        with (
            pytest.raises(SandboxValidationError, match="no function called 'score'"),
            ScoringSandbox("x = 1\n", validate=False),
        ):
            pass

    def test_validation_runs_before_any_process_starts(self):
        with pytest.raises(SandboxValidationError):
            ScoringSandbox("import os\ndef score(a, b):\n    return 0.0\n")

    def test_scoring_outside_the_context_manager_is_refused(self):
        sandbox = ScoringSandbox(TRIVIAL)
        with pytest.raises(SandboxCrashed, match="not running"):
            sandbox.score([{"board": [[False]], "placement": {}}])

    def test_close_is_idempotent(self):
        sandbox = ScoringSandbox(TRIVIAL)
        with sandbox:
            pass
        sandbox.close()

    def test_the_worker_is_shut_down_even_if_the_game_raises(self, items):
        sandbox = ScoringSandbox(TRIVIAL)
        with pytest.raises(RuntimeError), sandbox:
            sandbox.score(items[:1])
            raise RuntimeError("the game blew up")
        assert sandbox._process is None

    def test_failure_samples_are_capped(self, items):
        """A broken function must not accumulate thousands of error strings."""
        source = "def score(board, placement):\n    raise ValueError('nope')\n"
        with ScoringSandbox(source, validate=False) as sandbox:
            for _ in range(5):
                sandbox.score(items)
            assert sandbox.failures > 10
            assert len(sandbox.errors) == 10


class TestPureBuiltinsAreAvailable:
    """A missing pure builtin does not fail safe; it fails as an unplayable strategy.

    `ord` was absent, a model used `ord(placement["kind"])` as a tie-breaker, and
    every scoring call raised NameError. The engine played the first legal
    placement every turn and four iterations of a six-iteration run collapsed
    from a held-out 1,580 to 10 -- while looking like a plausible strategy that
    simply played badly.
    """

    def test_a_tie_breaker_using_ord_scores_normally(self) -> None:
        source = (
            "def score(board, placement):\n"
            "    return float(placement['lines_cleared']) + ord(placement['kind']) * 0.001\n"
        )
        game = Game(seed=1, max_pieces=50)
        items = build_items(game.board, game.legal_placements())
        with ScoringSandbox(source) as sandbox:
            scores = sandbox.score(items)
        assert sandbox.failures == 0
        assert all(s != UNPLAYABLE for s in scores)

    def test_the_pure_builtins_a_scoring_function_might_reach_for_all_exist(self) -> None:
        for call in ("ord('A')", "chr(65)", "str(1)", "hash(1)", "bin(2)", "hex(2)", "abs(-1)"):
            source = f"def score(board, placement):\n    return float(len(str({call})))\n"
            game = Game(seed=1, max_pieces=20)
            items = build_items(game.board, game.legal_placements())
            with ScoringSandbox(source) as sandbox:
                scores = sandbox.score(items[:1])
            assert sandbox.failures == 0, f"{call} failed: {sandbox.errors}"
            assert scores[0] != UNPLAYABLE

    def test_mro_is_refused_so_the_type_hierarchy_stays_out_of_reach(self) -> None:
        """Defence in depth: `__subclasses__` is already blocked as a dunder."""
        with pytest.raises(SandboxValidationError, match="mro"):
            validate_source("def score(board, placement):\n    return float(len(str.mro()))\n")
