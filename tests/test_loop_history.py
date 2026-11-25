"""Tests for the history arm: showing a chain its whole trajectory.

The single-step loop shows a model only its previous function and that one
attempt's outcome, which is a plausible cause of the "reweights rather than
debugs" behaviour the project measures. ``--history`` is the arm that tests it.

Three things here are load-bearing:

- **it is off by default**, because every published run was measured without it
  and a silently-enabled flag would make a new run incomparable;
- **the prompt template is untouched**, so the two arms differ by exactly one
  block and nothing else;
- **the scores shown are training scores.** Showing held-out scores would let a
  model tune against the set the curve is read from, which would quietly
  destroy the measurement rather than improve it.
"""

from __future__ import annotations

from tetris_bench.loop import LoopConfig, MultiOutcome, Outcome, build_prompt, history_section
from tetris_bench.records import GameResult


def result(score: int, pieces: int) -> GameResult:
    return GameResult(
        agent="strategy",
        seed=1,
        agent_seed=None,
        score=score,
        lines_cleared=score // 100,
        pieces_placed=pieces,
        cause="block_out",
        final_max_height=5,
        final_holes=1,
        final_bumpiness=2,
        final_aggregate_height=10,
        avg_max_height=5.0,
        avg_holes=1.0,
        avg_bumpiness=2.0,
    )


def played(source: str, score: int, pieces: int) -> MultiOutcome:
    outcome = Outcome(source=source, result=result(score, pieces))
    return MultiOutcome(source=source, per_seed={1: outcome})


# ------------------------------------------------------------------ rendering


def test_no_history_renders_nothing() -> None:
    assert history_section([]) == ""


def test_each_attempt_appears_oldest_first_with_its_rate() -> None:
    text = history_section(
        [
            played("def score(a, b): return 1.0", 100, 10),
            played("def score(a, b): return 2.0", 900, 30),
        ]
    )
    assert text.index("Attempt 0") < text.index("Attempt 1")
    assert "return 1.0" in text and "return 2.0" in text
    assert "10.00 per piece" in text  # 100 / 10
    assert "30.00 per piece" in text  # 900 / 30


def test_a_rejected_attempt_shows_its_reason_not_a_score() -> None:
    """A step that produced nothing is still a step worth seeing."""
    rejected = MultiOutcome(source="import math", rejected=True, reason="imports are not allowed")
    text = history_section([rejected])
    assert "imports are not allowed" in text
    assert "per piece" not in text


def test_an_attempt_with_no_source_says_so_rather_than_showing_an_empty_block() -> None:
    text = history_section([MultiOutcome(source="", rejected=True, reason="unparseable")])
    assert "no function was produced" in text
    assert "```python\n\n```" not in text


def test_a_zero_piece_attempt_does_not_divide_by_zero() -> None:
    assert "0.00 per piece" in history_section([played("def score(a, b): return 1.0", 0, 0)])


# ----------------------------------------------------------------- the switch


def test_history_is_off_by_default() -> None:
    assert LoopConfig(model="m").history is False


def test_the_block_is_absent_unless_the_flag_is_on() -> None:
    previous = played("def score(a, b): return 1.0", 100, 10)
    earlier = [played("def score(a, b): return 0.0", 10, 10)]
    off = build_prompt(LoopConfig(model="m"), previous, earlier)
    assert "Everything you have tried" not in off


def test_the_block_appears_when_the_flag_is_on() -> None:
    previous = played("def score(a, b): return 1.0", 100, 10)
    earlier = [played("def score(a, b): return 0.0", 10, 10)]
    on = build_prompt(LoopConfig(model="m", history=True), previous, earlier)
    assert "Everything you have tried" in on
    assert "return 0.0" in on


def test_the_two_arms_differ_by_the_history_block_alone() -> None:
    """The template is untouched, so the arm is a clean comparison."""
    previous = played("def score(a, b): return 1.0", 100, 10)
    earlier = [played("def score(a, b): return 0.0", 10, 10)]
    off = build_prompt(LoopConfig(model="m"), previous, earlier)
    on = build_prompt(LoopConfig(model="m", history=True), previous, earlier)
    assert len(on) > len(off)
    block = history_section(earlier)
    assert on.replace(block + "\n", "", 1) == off


def test_iteration_zero_is_identical_in_both_arms() -> None:
    """With nothing tried yet there is no history, so the arms cannot differ."""
    assert build_prompt(LoopConfig(model="m", history=True), None, []) == build_prompt(
        LoopConfig(model="m"), None, []
    )
