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

#: The fixture's default pieces per game. The headline is points per piece, so
#: every expectation below is written as `score / PIECES` rather than as a bare
#: number -- it keeps the arithmetic visible and survives a change of default.
PIECES = 50


def game(seed: int, score: int, pieces: int = PIECES, holes: int = 10) -> GameResult:
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
    assert curve.paired_deltas() == [(0, 1, 50 / PIECES), (1, 1, -100 / PIECES)]
    assert curve.mean_delta() == pytest.approx(-25 / PIECES)
    assert curve.regressions() == 1


def test_chains_are_combined_by_median() -> None:
    rows: list[dict] = []
    for chain, score in ((0, 100), (1, 200), (2, 900)):
        rows += position_rows(chain=chain, iteration=0, train=[(1, 0)], held_out=[(1000, score)])
    (curve,) = build_curves(rows)
    assert curve.median_score() == [200 / PIECES]


def test_a_rejected_position_contributes_a_zero_and_is_flagged() -> None:
    """A position with no eval rows never ran; it scores zero rather than vanishing."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 300)], held_out=[(1000, 300)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[], played=False),
    ]
    (curve,) = build_curves(rows)
    assert [p.iteration for p in curve.positions] == [0, 1]
    assert curve.median_score() == [300 / PIECES, 0.0]
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
    assert curve.median_score() == [100 / PIECES, 500 / PIECES, 200 / PIECES]
    assert curve.best_so_far() == [100 / PIECES, 500 / PIECES, 500 / PIECES]


def test_cost_per_point_is_none_when_nothing_was_gained() -> None:
    """A flat or falling curve has no cost per point, and must not report one."""
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 300)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 200)]),
    ]
    (curve,) = build_curves(rows)
    assert curve.score_gained() == pytest.approx(-100 / PIECES)
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
    assert curve.score_gained() == pytest.approx(200 / PIECES)
    # 1,000 tokens for 4 points of rate, and 50s for the same 4.
    assert curve.tokens_per_point() == pytest.approx(1_000 / (200 / PIECES))
    assert curve.seconds_per_point() == pytest.approx(50.0 / (200 / PIECES))


def test_plateau_needs_a_tolerance_and_finds_the_first_settled_iteration() -> None:
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)]),
        *position_rows(chain=0, iteration=1, train=[(1, 0)], held_out=[(1000, 500)]),
        *position_rows(chain=0, iteration=2, train=[(1, 0)], held_out=[(1000, 520)]),
    ]
    (curve,) = build_curves(rows)
    # Strict: only the actual maximum qualifies.
    assert curve.plateau_iteration(tolerance=0.0) == 2
    # Tolerances are in headline units now, so 100 points of score noise over a
    # 50-piece game is 2 points of rate. At that bar iteration 1 is already
    # indistinguishable from the end.
    assert curve.plateau_iteration(tolerance=100 / PIECES) == 1
    assert curve.plateau_iteration(tolerance=1_000 / PIECES) == 0


def test_models_are_separated() -> None:
    rows = [
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100)], model="a"),
        *position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 900)], model="b"),
    ]
    curves = build_curves(rows)
    assert [c.model for c in curves] == ["a", "b"]
    assert curves[0].median_score() == [100 / PIECES]
    assert curves[1].median_score() == [900 / PIECES]


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
    # Each position: rate 100/50 and 200/50, with the same spread either way --
    # the per-game rates are (0, 200)/50 and (100, 300)/50.
    assert curve.median_score() == [100 / PIECES, 200 / PIECES]
    assert curve.seed_noise() == curve.positions[0].eval_rate_sd
    assert curve.seed_noise() > 100 / PIECES
    # The score spread is still recorded, and is PIECES times larger. Keeping
    # both is the point: feeding the score spread to a rate threshold was the
    # unit error this switch had to avoid.
    assert curve.positions[0].eval_sd == pytest.approx(curve.positions[0].eval_rate_sd * PIECES)
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

    per_point = 1_000 / (200 / PIECES)
    assert single.tokens_per_point() == pytest.approx(per_point)
    assert triple.tokens_per_point() == pytest.approx(per_point)
    assert triple.total_tokens() == 3 * single.total_tokens()


def test_chain_spread_measures_disagreement_between_chains() -> None:
    rows: list[dict] = []
    for chain, score in ((0, 100), (1, 200), (2, 900)):
        rows += position_rows(chain=chain, iteration=0, train=[(1, 0)], held_out=[(1000, score)])
    (curve,) = build_curves(rows)
    assert curve.chain_spread() == pytest.approx(
        statistics.stdev([100 / PIECES, 200 / PIECES, 900 / PIECES])
    )
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


class TestTheHeadlineIsARate:
    """The switch from totals to points per piece, and the choices inside it."""

    def test_the_headline_is_total_points_over_total_pieces(self):
        # Not a mean of per-game ratios, which would give 2.841 here. The ratio
        # of totals is what the hand-written baseline's own 43.5 is
        # (454,900 / 10,467), so any other definition would compare the model
        # against a differently computed number.
        rows = position_rows(
            chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 100), (1001, 140)]
        )
        for row in rows:
            if row["split"] == "eval":
                row["pieces_placed"] = 40 if row["seed"] == 1000 else 44
        (curve,) = build_curves(rows)
        assert curve.positions[0].eval_rate == pytest.approx(240 / 84)
        assert curve.positions[0].headline == pytest.approx(240 / 84)
        assert curve.positions[0].eval_rate != pytest.approx((100 / 40 + 140 / 44) / 2)

    def test_the_total_is_still_recorded_beside_the_rate(self):
        # Survival and rate are separate things to know, and the README reports
        # both; switching the headline must not throw the total away.
        rows = position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 500)])
        (curve,) = build_curves(rows)
        assert curve.positions[0].eval_score == 500.0
        assert curve.positions[0].score == 500.0
        assert curve.positions[0].headline == pytest.approx(500 / PIECES)

    def test_a_rate_over_no_pieces_is_none_but_the_headline_is_zero(self):
        # Same split the module makes for board features: a position that never
        # played contributes a zero to the curve, because scoring nothing is a
        # real outcome, while the undefined rate itself stays None.
        rows = position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[], played=False)
        (curve,) = build_curves(rows)
        assert curve.positions[0].eval_rate is None
        assert curve.positions[0].headline == 0.0

    def test_the_rate_is_unaffected_by_where_a_game_was_cut_off(self):
        # The whole reason for the switch. Two positions with the same scoring
        # rate but very different lengths -- one censored early, one not -- are
        # the same headline, where their totals differ by a factor of four.
        short = position_rows(chain=0, iteration=0, train=[(1, 0)], held_out=[(1000, 500)])
        long_ = position_rows(chain=1, iteration=0, train=[(1, 0)], held_out=[(1000, 2000)])
        for row in short:
            if row["split"] == "eval":
                row["pieces_placed"] = 50
        for row in long_:
            if row["split"] == "eval":
                row["pieces_placed"] = 200
        (curve,) = build_curves([*short, *long_])
        rates = [p.headline for p in curve.positions]
        assert rates[0] == pytest.approx(rates[1])
        assert curve.positions[0].eval_score * 4 == curve.positions[1].eval_score
