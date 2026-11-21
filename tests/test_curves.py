"""Tests for the curve aggregation.

Rows are built through :class:`RunRecord` rather than written by hand, so these
exercise the schema the loop actually writes. A hand-written dict would keep
passing after a field was renamed.
"""

from __future__ import annotations

import math
import statistics

import pytest

from tetris_bench.curves import Curve, build_curves, summarise
from tetris_bench.records import GameResult, ModelUsage, RunRecord


def game(seed: int, score: int, pieces: int = 50, holes: int = 10) -> GameResult:
    return GameResult(
        agent="strategy",
        seed=seed,
        agent_seed=None,
        score=score,
        lines_cleared=score // 100,
        pieces_placed=pieces,
        cause="block_out",
        final_aggregate_height=40,
        final_max_height=12,
        final_bumpiness=8,
        final_holes=holes,
        avg_max_height=10.0,
        avg_bumpiness=7.0,
        avg_holes=float(holes),
    )


def position_rows(
    *,
    chain: int,
    iteration: int,
    train: list[tuple[int, int]],
    held_out: list[tuple[int, int]],
    tokens: int = 1_000,
    seconds: float = 10.0,
    model: str = "qwen3-14b",
    played: bool = True,
) -> list[dict]:
    """Rows for one position, with usage attributed the way the loop does it."""
    rows: list[dict] = []
    for index, (seed, score) in enumerate(train):
        usage = (
            ModelUsage(
                model_calls=1,
                tokens_in=tokens // 2,
                tokens_out=tokens - tokens // 2,
                latency_seconds=seconds,
            )
            if index == 0
            else ModelUsage()
        )
        rows.append(
            RunRecord(
                game=game(seed, score),
                model=model,
                mode="strategy",
                iteration=iteration,
                chain=chain,
                usage=usage,
                split="train",
                played=played,
            ).as_dict()
        )
    for seed, score in held_out:
        rows.append(
            RunRecord(
                game=game(seed, score),
                model=model,
                mode="strategy",
                iteration=iteration,
                chain=chain,
                usage=ModelUsage(),
                split="eval",
                played=played,
            ).as_dict()
        )
    return rows


def test_score_comes_from_eval_rows_not_train_rows() -> None:
    """The whole point of the split: a flattering training score must not surface."""
    rows = position_rows(
        chain=0,
        iteration=0,
        train=[(1, 400), (2, 400)],
        held_out=[(1000, 100), (1001, 120)],
    )
    (summary,) = summarise(rows)
    assert summary.eval_score == 110.0
    assert summary.train_score == 400.0
    assert summary.score == summary.eval_score


def test_usage_is_counted_once_per_position() -> None:
    """Three training seeds, one generation. Cost must not triple."""
    rows = position_rows(
        chain=0,
        iteration=0,
        train=[(1, 100), (2, 100), (17, 100)],
        held_out=[(1000, 100)],
        tokens=5_000,
        seconds=480.0,
    )
    (summary,) = summarise(rows)
    assert summary.tokens == 5_000
    assert summary.seconds == 480.0
    assert summary.model_calls == 1


def test_cost_survives_the_eval_only_trap() -> None:
    """Evaluation rows carry no usage, so a summary built from them alone is free.

    This is the mistake the aggregation exists to prevent: the honest curve lives
    on eval rows while the cost lives on train rows, and reading both off the
    same filtered subset silently reports a zero-token run.
    """
    rows = position_rows(
        chain=0, iteration=0, train=[(1, 100)], held_out=[(1000, 100)], tokens=5_000
    )
    eval_only = [r for r in rows if r["split"] == "eval"]
    assert sum(r["tokens_in"] + r["tokens_out"] for r in eval_only) == 0
    (summary,) = summarise(rows)
    assert summary.tokens == 5_000


def test_deltas_are_paired_within_a_chain() -> None:
    """Chain 1 starting high must not read as chain 0 having improved."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 150)]),
        *position_rows(chain=1, iteration=0, train=[(1, 0)], held_out=[(1000, 900)]),
        *position_rows(chain=1, iteration=1, train=[(1, 0)], held_out=[(1000, 800)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.paired_deltas() == [(0, 1, 50.0), (1, 1, -100.0)]
    assert curve.mean_delta() == -25.0
    assert curve.regressions() == 1


def test_chains_are_combined_by_median() -> None:
    rows: list[dict] = []
    for chain, score in ((0, 100), (1, 200), (2, 900)):
        rows += position_rows(chain=chain, iteration=0, train=[(1, 0)], held_out=[(1000, score)])
    (curve,) = build_curves(rows)
    assert curve.median_score() == [200.0]


def test_a_rejected_position_contributes_a_zero_and_is_flagged() -> None:
    """A position with no eval rows never ran; it scores zero rather than vanishing."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 300)], held_out=[(1000, 300)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[], played=False),
    ]
    (curve,) = build_curves(rows)
    assert [p.iteration for p in curve.positions] == [0, 1]
    assert curve.median_score() == [300.0, 0.0]
    assert curve.positions[1].rejected is True
    assert curve.positions[1].eval_games == 0
    assert curve.regressions() == 1


def test_best_so_far_never_falls() -> None:
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 500)]),
        *position_rows(chain=0, iteration=2, train=[(1, 0)], held_out=[(1000, 200)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.median_score() == [100.0, 500.0, 200.0]
    assert curve.best_so_far() == [100.0, 500.0, 500.0]


def test_cost_per_point_is_none_when_nothing_was_gained() -> None:
    """A flat or falling curve has no cost per point, and must not report one."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 300)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 200)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.score_gained() == -100.0
    assert curve.tokens_per_point() is None
    assert curve.seconds_per_point() is None


def test_cost_per_point_divides_total_cost_by_held_out_gain() -> None:
    rows = [
        *position_rows(
            chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)], tokens=400, seconds=20.0
        ),
        *position_rows(
            chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 300)], tokens=600, seconds=30.0
        ),
    ]
    (curve,) = build_curves(rows)
    assert curve.total_tokens() == 1_000
    assert curve.score_gained() == 200.0
    assert curve.tokens_per_point() == 5.0
    assert curve.seconds_per_point() == 0.25


def test_plateau_needs_a_tolerance_and_finds_the_first_settled_iteration() -> None:
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 500)]),
        *position_rows(chain=0, iteration=2, train=[(1, 0)], held_out=[(1000, 520)]),
    ]
    (curve,) = build_curves(rows)
    # Strict: only the actual maximum qualifies.
    assert curve.plateau_iteration(tolerance=0.0) == 2
    # With 100 points of noise, iteration 1 is already indistinguishable from the end.
    assert curve.plateau_iteration(tolerance=100.0) == 1
    assert curve.plateau_iteration(tolerance=1_000.0) == 0


def test_models_are_separated() -> None:
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)], model="a"),
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 900)], model="b"),
    ]
    curves = build_curves(rows)
    assert [c.model for c in curves] == ["a", "b"]
    assert curves[0].median_score() == [100.0]
    assert curves[1].median_score() == [900.0]


def test_non_strategy_rows_are_ignored() -> None:
    baseline = RunRecord(
        game=game(1, 21_600), model="heuristic", mode="baseline", iteration=0
    ).as_dict()
    rows = [baseline, *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)])]
    (curve,) = build_curves(rows)
    assert curve.model == "qwen3-14b"


def test_empty_log_yields_no_curves() -> None:
    assert build_curves([]) == []
    assert Curve(model="x", positions=[]).median_score() == []
    assert Curve(model="x", positions=[]).plateau_iteration(tolerance=1.0) is None


def test_held_out_spread_is_measured_and_drives_the_plateau_threshold() -> None:
    """The plateau tolerance must come from the data, not from a chosen constant."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 0), (1001, 200)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 100), (1001, 300)]),
    ]
    (curve,) = build_curves(rows)
    # Each position: mean 100 and 200, sd of (0, 200) and (100, 300) alike.
    assert curve.median_score() == [100.0, 200.0]
    assert curve.seed_noise() == curve.positions[0].eval_sd
    assert curve.seed_noise() > 100.0
    # The plotted point is a mean of two games, so its own spread is smaller by
    # root-2. Judging a mean against a single-game spread sets the bar too high.
    assert curve.noise_of_mean() == pytest.approx(curve.seed_noise() / math.sqrt(2))
    assert curve.plateau_iteration(curve.seed_noise()) == 0
    assert curve.plateau_iteration(tolerance=0.0) == 1


def test_a_single_held_out_game_reports_no_spread_rather_than_failing() -> None:
    rows = position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)])
    (summary,) = summarise(rows)
    assert summary.eval_sd == 0.0
    assert Curve(model="m", positions=[summary]).seed_noise() == 0.0
    assert Curve(model="m", positions=[summary]).noise_of_mean() == 0.0


def test_duplicate_rows_do_not_double_a_position_cost() -> None:
    """Concatenating two logs must not silently inflate tokens.

    Cost is summed over a position's rows while scores are averaged, so a
    duplicate doubles the cost and leaves every score looking correct.
    """
    rows = position_rows(
        chain=0, iteration=0, train=[(1, 100)], held_out=[(1000, 100)], tokens=5_000
    )
    (once,) = summarise(rows)
    (twice,) = summarise([*rows, *rows])
    assert once.tokens == twice.tokens == 5_000
    assert once.eval_score == twice.eval_score


def test_board_features_are_none_when_no_held_out_game_ran() -> None:
    """Zero holes reads as a flawless board, so an absent board must not be zero."""
    rows = position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[], played=False)
    (summary,) = summarise(rows)
    assert summary.eval_games == 0
    assert summary.eval_holes is None
    assert summary.eval_pieces is None
    # The score still carries a real zero: scoring nothing is an outcome.
    assert summary.eval_score == 0.0


def test_cost_per_point_does_not_scale_with_the_number_of_chains() -> None:
    """The same per-chain behaviour must cost the same per point at 1 chain or 3.

    Dividing total cost by the gain in the median charges every lineage's tokens
    against one lineage's improvement, so a rung run at 5 chains would look five
    times more expensive than the same rung at 1 — purely from the sampling
    budget, in a table that compares models.
    """

    def one_chain(chain: int) -> list[dict]:
        return [
            *position_rows(
                chain=chain, iteration=0, train=[(1, 0)], held_out=[(1000, 100)], tokens=400
            ),
            *position_rows(
                chain=chain, iteration=1, train=[(1, 0)], held_out=[(1000, 300)], tokens=600
            ),
        ]

    (single,) = build_curves(one_chain(0))
    (triple,) = build_curves([*one_chain(0), *one_chain(1), *one_chain(2)])

    assert single.tokens_per_point() == 5.0
    assert triple.tokens_per_point() == 5.0
    assert triple.total_tokens() == 3 * single.total_tokens()


def test_chain_spread_measures_disagreement_between_chains() -> None:
    rows: list[dict] = []
    for chain, score in ((0, 100), (1, 200), (2, 900)):
        rows += position_rows(chain=chain, iteration=0, train=[(1, 0)], held_out=[(1000, score)])
    (curve,) = build_curves(rows)
    assert curve.chain_spread() == pytest.approx(statistics.stdev([100, 200, 900]))
    # Generation noise dominates, so it is the bar for a delta.
    assert curve.delta_noise() == curve.chain_spread()


def test_delta_noise_falls_back_to_seed_noise_with_one_chain() -> None:
    """A single chain cannot see generation noise, and the bar says so by being small."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 0), (1001, 200)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.chain_spread() == 0.0
    assert curve.delta_noise() == curve.noise_of_mean() > 0.0


def test_incomplete_and_unlogged_positions_are_reported_separately() -> None:
    rows = [
        *position_rows(
            chain=0,
            iteration=0,
            train=[(1, 0)],
            held_out=[(1000 + i, 100) for i in range(10)],
        ),
        # A kill between the train and eval writes: three of ten games logged.
        *position_rows(
            chain=0, iteration=1, train=[(1, 0)], held_out=[(1000 + i, 100) for i in range(3)]
        ),
        # A crash on the first eval seed: train rows say played, no eval rows.
        *position_rows(chain=0, iteration=2, train=[(1, 0)], held_out=[]),
    ]
    (curve,) = build_curves(rows)
    assert [p.iteration for p in curve.incomplete_positions()] == [1]
    assert [p.iteration for p in curve.unlogged_positions()] == [2]
    # This is the unflagged zero: played is True, so `rejected` cannot catch it.
    unlogged = curve.unlogged_positions()[0]
    assert unlogged.rejected is False
    assert unlogged.eval_games == 0


def test_plateau_reports_the_peak_not_the_last_value() -> None:
    """A curve that peaks and collapses must not read as having settled."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 2000)]),
        *position_rows(chain=0, iteration=2, train=[(1, 0)], held_out=[(1000, 100)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.plateau_iteration(tolerance=0.0) == 1
    # score_gained is signed, so the collapse is visible beside the plateau.
    assert curve.score_gained() == 0.0
    assert curve.regressions() == 1


def test_cost_is_summarised_correctly_from_rows_the_loop_itself_wrote(tmp_path) -> None:
    """The one test that would catch the loop changing its usage attribution.

    Every other test here builds rows through a helper that hard-codes zero
    usage on eval rows, so an assertion that eval rows are free is a fact about
    the helper. This writes through `loop._log_multi`, so if the loop ever
    repeated usage on each row, the summarised cost would be wrong and this
    would fail.
    """
    from tetris_bench.loop import LoopConfig, MultiOutcome, Outcome, Position, _log_multi
    from tetris_bench.records import ModelUsage

    config = LoopConfig(
        model="m", train_seeds=(1, 2, 17), eval_seeds=(1000, 1001), log_path=tmp_path / "l.jsonl"
    )
    multi = MultiOutcome(source="x")
    for seed in config.train_seeds:
        multi.per_seed[seed] = Outcome(source="x", result=game(seed, 100))
    held = MultiOutcome(source="x")
    for seed in config.eval_seeds:
        held.per_seed[seed] = Outcome(source="x", result=game(seed, 50))

    usage = ModelUsage(model_calls=1, tokens_in=1_000, tokens_out=4_000, latency_seconds=480.0)
    _log_multi(config, Position(0, 0), multi, usage, "train")
    _log_multi(config, Position(0, 0), held, ModelUsage(), "eval")

    from tetris_bench.jsonl import read_records

    (summary,) = summarise(read_records(config.log_path))
    assert summary.train_games == 3
    assert summary.eval_games == 2
    assert summary.tokens == 5_000
    assert summary.seconds == 480.0
    assert summary.model_calls == 1
    assert summary.eval_score == 50.0
