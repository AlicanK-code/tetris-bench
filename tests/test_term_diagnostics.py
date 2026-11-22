"""Tests for the strategy-capability probes.

The first class tests the *instrument* rather than any function: if the probe
boards are not what they claim, every verdict drawn from them is worthless. That
is the test this module most needs, because a probe pair whose "better" board is
not actually better would quietly invert every conclusion.
"""

from __future__ import annotations

from tetris_bench.term_diagnostics import (
    BLIND,
    FAILED,
    INVERTED,
    OK,
    Verdict,
    classify,
    flat,
    flip,
    flipped_probes,
    is_upside_down,
    judge,
    probes,
    sources,
    terms_that_flip,
)

# A correct scorer: row 0 is the top, so height is measured downward from it.
CORRECT = """
def score(board, placement):
    total_height = 0
    holes = 0
    for col in range(10):
        seen = False
        for row in range(20):
            if board[row][col]:
                if not seen:
                    total_height += 20 - row
                seen = True
            elif seen:
                holes += 1
    return float(placement["lines_cleared"] * 1000 - total_height * 5 - holes * 20)
"""

# The exact bug from chains 1 and 4: free space above the stack counted as holes,
# so a short column is punished and the function builds upward.
INVERTED_SOURCE = """
def score(board, placement):
    holes = 0
    for col in range(10):
        for row in range(20):
            if board[row][col]:
                break
            holes += 1
    return float(placement["lines_cleared"] * 1000 - holes * 50)
"""

# The exact bug from chains 0 and 3: a top-down scan that breaks on the first
# empty cell, so every height term is identically zero.
DEAD_SOURCE = """
def score(board, placement):
    heights = []
    for col in range(10):
        h = 0
        for row in range(20):
            if board[row][col]:
                h += 1
            else:
                break
        heights.append(h)
    return float(placement["lines_cleared"] * 1000 - sum(heights) * 10 - max(heights) * 5)
"""


class TestTheProbesThemselves:
    def test_the_better_board_really_is_shallower(self):
        height = next(p for p in probes() if p.name == "height")
        assert _depth(height.better["board"]) < _depth(height.worse["board"])

    def test_no_probe_board_contains_a_completed_row(self):
        # A full row would have been cleared by the engine, so a board holding
        # one is not a position any placement could actually produce.
        for probe in probes():
            for half in (probe.better, probe.worse):
                assert not any(all(row) for row in half["board"])

    def test_the_two_halves_differ_only_in_the_board_or_the_lines(self):
        for probe in probes():
            better, worse = probe.better["placement"], probe.worse["placement"]
            ignoring_lines = {k: v for k, v in better.items() if k != "lines_cleared"}
            assert ignoring_lines == {k: v for k, v in worse.items() if k != "lines_cleared"}

    def test_flipping_twice_is_the_identity(self):
        assert flip(flip(flat(4))) == flat(4)

    def test_the_flipped_probes_are_actually_flipped(self):
        for upright, upside_down in zip(probes(), flipped_probes(), strict=True):
            assert upside_down.better["board"] == flip(upright.better["board"])


class TestJudging:
    def test_a_higher_score_for_the_better_board_is_ok(self):
        assert judge(10, 5) == OK

    def test_an_equal_score_is_blind_not_wrong(self):
        assert judge(5, 5) == BLIND

    def test_preferring_the_worse_board_is_inverted(self):
        assert judge(5, 10) == INVERTED


class TestClassifyingRealBugs:
    def test_a_correct_function_passes_every_probe(self):
        assert classify(CORRECT, "correct").strategy_capable

    def test_a_correct_function_must_invert_when_flipped(self):
        # The control that keeps the flip test honest: if a correct function did
        # NOT invert on upside-down boards, the flip would be measuring nothing.
        flipped = classify(CORRECT, "correct", flipped_probes())
        assert flipped.answers["height"] == INVERTED

    def test_the_inverted_hole_counter_is_caught(self):
        verdict = classify(INVERTED_SOURCE, "inverted")
        assert verdict.answers["height"] == INVERTED
        assert not verdict.strategy_capable

    def test_the_inverted_hole_counter_is_wrong_both_ways_up(self):
        # Not a convention error: flipping it makes the term inert rather than
        # correct, because it scans from row 0 and a flipped board is filled
        # there. So it is genuinely confused, not merely upside down.
        assert not is_upside_down(INVERTED_SOURCE)
        assert terms_that_flip(INVERTED_SOURCE) == []

    def test_a_dead_height_term_is_bottom_origin_code(self):
        # The finer test earns its keep here. The whole function never becomes
        # correct -- it has no hole term in either orientation -- but its height
        # loop is right if row 0 is the floor, which is why it is dead upright.
        assert not is_upside_down(DEAD_SOURCE)
        assert terms_that_flip(DEAD_SOURCE) == ["height"]

    def test_a_dead_height_term_reads_blind_not_inverted(self):
        # The distinction matters: blind means the term cannot vary at all,
        # which no change of weight can fix.
        verdict = classify(DEAD_SOURCE, "dead")
        assert verdict.answers["height"] == BLIND
        assert not verdict.strategy_capable

    def test_a_correct_function_is_not_upside_down(self):
        assert not is_upside_down(CORRECT)

    def test_lines_are_preferred_by_all_three_examples(self):
        # Every one of these gets `lines_cleared` right, which is the finding:
        # the harness-specific fact caused no errors, the geometry did.
        for source in (CORRECT, INVERTED_SOURCE, DEAD_SOURCE):
            assert classify(source, "x").answers["lines"] == OK


class TestWhenAFunctionWillNotRun:
    def test_a_syntax_error_is_recorded_rather_than_raised(self):
        verdict = classify("def score(board, placement) this is not python", "bad")
        assert set(verdict.answers.values()) == {FAILED}
        assert not verdict.strategy_capable

    def test_a_rejected_import_is_recorded_too(self):
        verdict = classify("import os\ndef score(board, placement):\n    return 1.0\n", "bad")
        assert set(verdict.answers.values()) == {FAILED}


class TestVerdict:
    def test_broken_terms_names_only_the_failures(self):
        verdict = Verdict("x", {"height": OK, "holes": INVERTED, "lines": BLIND})
        assert verdict.broken_terms == ["holes", "lines"]

    def test_a_clean_verdict_has_no_broken_terms(self):
        assert Verdict("x", {"height": OK}).broken_terms == []


class TestReadingADirectory:
    def test_sources_are_yielded_in_a_stable_order(self, tmp_path):
        for name in ("c", "a", "b"):
            (tmp_path / f"{name}.py").write_text("def score(b, p):\n    return 0.0\n")
        assert [label for label, _ in sources(tmp_path)] == ["a", "b", "c"]

    def test_non_python_files_are_ignored(self, tmp_path):
        (tmp_path / "f.py").write_text("def score(b, p):\n    return 0.0\n")
        (tmp_path / "f.json").write_text("{}")
        assert len(list(sources(tmp_path))) == 1


def _depth(board) -> int:
    """How many rows down the first filled cell is, counted from the floor."""
    for index, row in enumerate(board):
        if any(row):
            return len(board) - index
    return 0
