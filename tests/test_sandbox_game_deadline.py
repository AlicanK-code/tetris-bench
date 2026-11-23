"""Tests for the whole-game time budget.

The gap this closes is specific and was easy to miss: bounding the call and
bounding the piece does not bound the game. A function that returns from every
call, well inside ``per_call_seconds``, can still take hours over 2000 pieces.
So the test that matters most here is not "a slow function is stopped" but
:meth:`TestItCatchesWhatTheOtherBudgetsMiss.test_a_function_that_never_times_out_per_call_is_still_stopped`
-- a function that is *individually* compliant and *cumulatively* pathological.
"""

from __future__ import annotations

import time

import pytest

from tetris_bench.sandbox import (
    SandboxCrashed,
    SandboxGameDeadline,
    SandboxLimits,
    ScoringSandbox,
)

# Returns promptly every single call, so per_call_seconds never fires.
QUICK = """
def score(board, placement):
    return float(placement["lines_cleared"])
"""

# Sleeps are impossible in the sandbox (no imports, no `time`), so cumulative
# slowness has to be bought with real work: ~200k operations a call.
SLOW = """
def score(board, placement):
    total = 0
    for _ in range(200):
        for row in board:
            for cell in row:
                if cell:
                    total += 1
    return float(total)
"""


def _item() -> dict:
    return {
        "board": [[False] * 10 for _ in range(20)],
        "placement": {
            "kind": "O",
            "rotation": 0,
            "column": 0,
            "row": 0,
            "cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
            "lines_cleared": 0,
        },
    }


class TestTheBudgetIsEnforced:
    def test_an_expired_budget_refuses_more_work(self):
        # A budget this small is already spent by the time scoring starts.
        limits = SandboxLimits(per_game_seconds=0.001)
        with ScoringSandbox(QUICK, limits) as box:
            time.sleep(0.01)
            with pytest.raises(SandboxGameDeadline) as caught:
                box.score([_item()])
        assert "budget" in str(caught.value)

    def test_the_message_names_the_budget_and_the_elapsed_time(self):
        limits = SandboxLimits(per_game_seconds=0.001)
        with ScoringSandbox(QUICK, limits) as box:
            time.sleep(0.01)
            with pytest.raises(SandboxGameDeadline) as caught:
                box.score([_item()])
        message = str(caught.value)
        assert "0.001s" in message
        assert "too slow" in message

    def test_a_generous_budget_does_not_interfere(self):
        with ScoringSandbox(QUICK, SandboxLimits(per_game_seconds=60.0)) as box:
            assert box.score([_item()]) == [0.0]

    def test_none_means_no_limit(self):
        with ScoringSandbox(QUICK, SandboxLimits(per_game_seconds=None)) as box:
            time.sleep(0.01)
            assert box.score([_item()]) == [0.0]

    def test_an_empty_batch_is_not_an_opportunity_to_fail(self):
        # score([]) returns before any budget check, so a finished game cannot
        # be turned into a deadline failure by a stray empty call.
        limits = SandboxLimits(per_game_seconds=0.001)
        with ScoringSandbox(QUICK, limits) as box:
            time.sleep(0.01)
            assert box.score([]) == []


class TestItCatchesWhatTheOtherBudgetsMiss:
    def test_a_function_that_never_times_out_per_call_is_still_stopped(self):
        # The whole point. Every call completes inside its own budget, so
        # per_call_seconds reports no failures at all -- and the game is still
        # stopped, because cumulatively it cannot finish.
        limits = SandboxLimits(per_call_seconds=5.0, per_game_seconds=0.25)
        with ScoringSandbox(SLOW, limits) as box, pytest.raises(SandboxGameDeadline):
            for _ in range(500):
                box.score([_item()] * 4)
        assert box.failures == 0, "no individual call timed out; only the game did"


class TestHowCallersSeeIt:
    def test_it_is_a_sandbox_crash_so_existing_handlers_still_catch_it(self):
        # Load-bearing: every caller already treats SandboxCrashed as "this
        # game is over, record it, keep the sweep alive". Inheriting means a
        # deadline cannot escape through a handler nobody added.
        assert issubclass(SandboxGameDeadline, SandboxCrashed)
        limits = SandboxLimits(per_game_seconds=0.001)
        with ScoringSandbox(QUICK, limits) as box:
            time.sleep(0.01)
            with pytest.raises(SandboxCrashed):
                box.score([_item()])

    def test_a_wedge_is_not_reported_as_a_deadline(self):
        # The converse: the generic crash must stay distinguishable, or the
        # feedback would hand the model the wrong diagnosis.
        assert not issubclass(SandboxCrashed, SandboxGameDeadline)


class TestElapsedSeconds:
    def test_it_is_zero_before_the_worker_starts(self):
        assert ScoringSandbox(QUICK).elapsed_seconds == 0.0

    def test_it_advances_once_running(self):
        with ScoringSandbox(QUICK) as box:
            time.sleep(0.01)
            assert box.elapsed_seconds > 0.0


class TestTheDefault:
    def test_the_default_budget_is_set_and_finite(self):
        # A default of None would mean the gap was documented and left open.
        budget = SandboxLimits().per_game_seconds
        assert budget is not None
        assert budget > 0

    def test_the_default_is_far_above_a_real_game(self):
        # Measured on the size ladder: 728 sandboxed games in ~92s, so ~0.13s
        # each. The budget should not be a figure a plausible function competes
        # with, or it becomes a measurement rather than a safety net.
        assert SandboxLimits().per_game_seconds >= 100 * 0.13


class TestWhatTheModelIsTold:
    """A deadline and a wedge must not produce the same feedback.

    The wedge text says "the usual cause is a loop that does not terminate".
    For a function that hits the game budget that is an actively wrong
    diagnosis -- it returns from every call -- and the project's rule is that
    feedback carries symptoms, never diagnoses, precisely so the model has to
    locate its own defect.
    """

    @staticmethod
    def _config(tmp_path):
        from tetris_bench.loop import LoopConfig

        return LoopConfig(
            model="fake",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=1,
            chains=1,
            max_pieces=60,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )

    def test_a_deadline_does_not_blame_a_nonterminating_loop(self, tmp_path):
        from tetris_bench.loop import Outcome, feedback_text

        outcome = Outcome(
            source=QUICK, crashed=True, deadline=True, reason="the game exceeded its 300s budget"
        )
        text = feedback_text(outcome, self._config(tmp_path))
        assert "ran out of time" in text
        assert "not a loop that never ends" in text
        assert "does not terminate" not in text

    def test_a_wedge_still_blames_a_nonterminating_loop(self, tmp_path):
        from tetris_bench.loop import Outcome, feedback_text

        outcome = Outcome(source=QUICK, crashed=True, reason="worker stopped answering")
        text = feedback_text(outcome, self._config(tmp_path))
        assert "does not terminate" in text
        assert "ran out of time" not in text

    def test_the_deadline_reason_reaches_the_model(self, tmp_path):
        from tetris_bench.loop import Outcome, feedback_text

        outcome = Outcome(source=QUICK, crashed=True, deadline=True, reason="ELAPSED-MARKER-42")
        assert "ELAPSED-MARKER-42" in feedback_text(outcome, self._config(tmp_path))
