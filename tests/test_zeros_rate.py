"""Tests for the dead-function proportion analysis.

The arithmetic is small but every piece of it is load-bearing for a published
claim, and two of the pieces are easy to get subtly wrong: pairing must happen
*within* a chain, and the sign test must use only the pairs that changed state.
Both are pinned here.
"""

from __future__ import annotations

import pytest

from tetris_bench.zeros_rate import (
    RANDOM_CEILING,
    Transitions,
    chains_needed,
    count_transitions,
    is_dead,
    sign_test,
)


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (0.0, True),
        (0.44, True),
        (RANDOM_CEILING, True),  # the boundary counts as dead
        (0.8511, False),
        (1.29, False),
        (43.5, False),
    ],
)
def test_is_dead_is_inclusive_at_the_ceiling(rate: float, expected: bool) -> None:
    assert is_dead(rate) is expected


def test_the_ceiling_sits_above_random_s_average_and_below_a_weak_function() -> None:
    """Documents what the constant is, so a casual edit has to confront it."""
    assert 0.327 < RANDOM_CEILING < 1.163


def test_transitions_are_counted_within_a_chain_not_across_chains() -> None:
    """Two chains that each stay put must not read as a change at the seam.

    Chain 0 ends dead and chain 1 begins alive. Concatenating them would
    manufacture one revival that no revision produced.
    """
    series = [[0.0, 0.0], [5.0, 5.0]]
    assert count_transitions(series) == Transitions(revivals=0, deaths=0)


def test_a_revival_and_a_death_are_counted_separately() -> None:
    series = [[0.0, 5.0], [5.0, 0.0]]
    t = count_transitions(series)
    assert (t.revivals, t.deaths) == (1, 1)
    assert t.discordant == 2


def test_every_adjacent_pair_counts_not_just_first_to_last() -> None:
    """A chain that dies, revives and dies again contributes three changes."""
    t = count_transitions([[5.0, 0.0, 5.0, 0.0]])
    assert (t.revivals, t.deaths) == (1, 2)


def test_a_chain_that_never_changes_state_contributes_nothing() -> None:
    t = count_transitions([[0.0, 0.1, 0.44], [10.0, 20.0, 30.0]])
    assert t.discordant == 0
    assert t.p_value == 1.0


def test_no_discordant_pairs_is_not_evidence_of_no_effect() -> None:
    """p = 1.0 rather than 0.0, which an "all pairs" denominator would give."""
    assert Transitions(revivals=0, deaths=0).p_value == 1.0


@pytest.mark.parametrize(
    ("successes", "trials", "expected"),
    [
        (5, 10, 1.0),
        (2, 4, 1.0),
        (10, 10, pytest.approx(2 / 1024)),
        (0, 10, pytest.approx(2 / 1024)),
        (0, 0, 1.0),
    ],
)
def test_sign_test(successes: int, trials: int, expected: float) -> None:
    assert sign_test(successes, trials) == expected


def test_the_sign_test_is_symmetric() -> None:
    assert sign_test(3, 10) == sign_test(7, 10)


def test_an_even_split_is_the_least_surprising_outcome() -> None:
    """Pins the direction of the test, so an inverted comparison would fail."""
    assert sign_test(5, 10) > sign_test(4, 10) > sign_test(3, 10)


def test_a_larger_effect_needs_fewer_chains() -> None:
    weak = chains_needed(0.40, 0.70, trials=400)
    strong = chains_needed(0.40, 0.90, trials=400)
    assert weak is not None and strong is not None
    assert strong < weak


def test_rarer_state_changes_need_more_chains() -> None:
    """Power comes from discordant pairs, so a stabler loop is harder to judge."""
    often = chains_needed(0.40, 0.80, trials=400)
    rarely = chains_needed(0.10, 0.80, trials=400)
    assert often is not None and rarely is not None
    assert rarely > often


def test_chains_needed_reports_failure_rather_than_a_misleading_number() -> None:
    """At the null there is no effect to find, so no sample size suffices."""
    assert chains_needed(0.40, 0.50, trials=200, limit=40) is None


def test_pairs_per_chain_is_what_converts_pairs_into_chains() -> None:
    """A longer chain yields more pairs, so fewer chains buy the same power.

    This is the parameter that was wrong on the first pass: counting discordant
    pairs and then dividing by chains treats one pair per chain, which
    understates how much a six-iteration chain contributes.
    """
    short = chains_needed(0.20, 0.90, pairs_per_chain=1, trials=400)
    long_ = chains_needed(0.20, 0.90, pairs_per_chain=5, trials=400)
    assert short is not None and long_ is not None
    assert long_ < short
