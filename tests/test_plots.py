"""Tests for the plotting layer.

Skipped when matplotlib is absent, because it lives in the optional ``analysis``
extra and a plain ``uv sync`` must still give a green test run.

What is worth testing here is not the pixels but the two places the drawing code
decides what a number *means*: how a position with no held-out game enters each
panel, and whether the panels agree with the table they sit beside. The figure
rendering itself gets one smoke test, since a crash there is loud and a layout
regression is not something an assertion can see.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib", reason="the analysis extra is not installed")

from tetris_bench.curves import build_curves  # noqa: E402
from tetris_bench.records import GameResult, ModelUsage, RunRecord  # noqa: E402


def _load_plots():
    """Import ``analysis/plots.py`` by path.

    ``analysis/`` is a folder of scripts rather than an installed package, and it
    is worth keeping it that way: packaging it only so that a test can import it
    would make the test drive the layout of the project.
    """
    path = Path(__file__).resolve().parents[1] / "analysis" / "plots.py"
    spec = importlib.util.spec_from_file_location("tetris_plots", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because `@dataclass` looks its own class's
    # module up in sys.modules while the class body is being processed.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


plots = _load_plots()


def game(seed: int, score: int, pieces: int) -> GameResult:
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
        final_holes=10,
        avg_max_height=10.0,
        avg_bumpiness=7.0,
        avg_holes=10.0,
    )


def position_rows(
    *,
    chain: int,
    iteration: int,
    held_out: list[tuple[int, int, int]],
    model: str = "qwen3-14b",
    played: bool = True,
    train: list[tuple[int, int, int]] | None = None,
) -> list[dict]:
    """Rows for one position, with usage attributed the way the loop does it."""
    train = train if train is not None else [(1, 0, 10)]
    rows: list[dict] = []
    for index, (seed, score, pieces) in enumerate(train):
        rows.append(
            RunRecord(
                game=game(seed, score, pieces),
                model=model,
                mode="strategy",
                iteration=iteration,
                chain=chain,
                usage=ModelUsage(model_calls=1, tokens_in=500, tokens_out=500)
                if index == 0
                else ModelUsage(),
                split="train",
                played=played,
            ).as_dict()
        )
    for seed, score, pieces in held_out:
        rows.append(
            RunRecord(
                game=game(seed, score, pieces),
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


def panels(rows: list[dict]):
    """The (score, pieces) panels for the one model in these rows."""
    (curve,) = build_curves(rows)
    values = plots.held_out_values(rows, "pieces_placed")
    return curve, plots.panels_for(curve, values)


def test_a_rejected_position_scores_zero_pieces_but_a_missing_one_has_no_value():
    """The two kinds of empty held-out set are different claims about the world.

    A rejected function placed no pieces, which is a real zero. A position whose
    held-out games are absent from the log placed an unknown number, and
    imputing a zero there would invent the worst possible result out of a gap.
    """
    rows = [
        *position_rows(chain=0, iteration=0, held_out=[(1000, 100, 40), (1001, 140, 44)]),
        # Rejected: the loop logs training rows with played=False and no eval.
        *position_rows(chain=0, iteration=1, held_out=[], played=False),
        # Played its training seeds, but the eval rows never reached the log.
        *position_rows(chain=0, iteration=2, held_out=[], played=True),
    ]
    _, (score, pieces) = panels(rows)

    assert score.per_chain[0] == [120.0, 0.0, 0.0]
    assert pieces.per_chain[0] == [42.0, 0.0, None]
    assert score.rejected == [(0, 1)] and score.unlogged == [(0, 2)]


def test_the_score_panel_median_is_the_one_the_table_prints():
    """The figure and ``analysis/curves.py`` must not be able to disagree."""
    rows = [
        *position_rows(chain=0, iteration=0, held_out=[(1000, 100, 30)]),
        *position_rows(chain=1, iteration=0, held_out=[(1000, 300, 50)]),
        *position_rows(chain=2, iteration=0, held_out=[(1000, 900, 70)]),
        *position_rows(chain=0, iteration=1, held_out=[(1000, 400, 40)]),
        *position_rows(chain=1, iteration=1, held_out=[], played=False),
        *position_rows(chain=2, iteration=1, held_out=[(1000, 800, 60)]),
    ]
    curve, (score, _) = panels(rows)
    assert score.median == curve.median_score()
    # The rejected chain's zero is in that median, so it is a median of three.
    assert score.median == [300.0, 400.0]


def test_the_pieces_median_leaves_out_a_position_with_no_games():
    """A missing value must not drag the median, and must not be imputed either."""
    rows = [
        *position_rows(chain=0, iteration=0, held_out=[(1000, 100, 30)]),
        *position_rows(chain=1, iteration=0, held_out=[(1000, 300, 50)]),
        # No eval rows and not rejected: pieces is unknown for this position.
        *position_rows(chain=2, iteration=0, held_out=[], played=True),
    ]
    _, (score, pieces) = panels(rows)
    assert pieces.median == [40.0]  # the median of 30 and 50, not of 30, 50 and 0
    assert score.median == [100.0]  # but the score keeps the logged zero


def test_a_short_held_out_set_keeps_its_value_and_gains_a_flag():
    """`play_on_seeds` keeps the games that finished before a crash, so a
    position can legitimately hold 3 of 10 held-out games. That mean is real,
    and noisier than its neighbours, so it is marked rather than dropped."""
    full = [(1000 + i, 100, 40) for i in range(10)]
    short = [(1000, 200, 60), (1001, 400, 80), (1002, 300, 70)]
    rows = [
        *position_rows(chain=0, iteration=0, held_out=full),
        *position_rows(chain=0, iteration=1, held_out=short),
    ]
    curve, (score, pieces) = panels(rows)

    assert [(p.chain, p.iteration) for p in curve.incomplete_positions()] == [(0, 1)]
    assert score.under_sampled == [(0, 1, 3)]
    assert score.per_chain[0] == [100.0, 300.0]
    assert pieces.per_chain[0] == [40.0, 70.0]
    # Short, but not empty: it is not one of the two failure flags.
    assert score.rejected == [] and score.unlogged == []


def test_pieces_noise_takes_the_larger_of_generation_and_seed_noise():
    """Chains that disagree set the bar, because generation noise dominates."""
    agreeing = [
        *position_rows(chain=0, iteration=0, held_out=[(1000, 100, 40), (1001, 100, 42)]),
        *position_rows(chain=1, iteration=0, held_out=[(1000, 100, 41), (1001, 100, 43)]),
    ]
    disagreeing = [
        *position_rows(chain=0, iteration=0, held_out=[(1000, 100, 20), (1001, 100, 22)]),
        *position_rows(chain=1, iteration=0, held_out=[(1000, 100, 90), (1001, 100, 92)]),
    ]
    for rows, expect_generation in ((agreeing, False), (disagreeing, True)):
        (curve,) = build_curves(rows)
        delta, mean = plots.pieces_noise(curve, plots.held_out_values(rows, "pieces_placed"))
        assert delta >= mean
        # Chains 70 pieces apart: the bar is their disagreement, not seed spread.
        assert (delta > mean * 5) is expect_generation


def test_the_ladder_is_ordered_by_size_not_by_name():
    rows: list[dict] = []
    for model in ("qwen3-30b", "qwen3-4b", "qwen3-14b"):
        rows += position_rows(chain=0, iteration=0, held_out=[(1000, 100, 40)], model=model)
    curves = build_curves(rows)
    assert [c.model for c in sorted(curves, key=plots.ladder_order)] == [
        "qwen3-4b",
        "qwen3-14b",
        "qwen3-30b",
    ]


def test_figures_render(tmp_path):
    """A smoke test: the drawing code has to survive every flag at once."""
    rows: list[dict] = []
    for model in ("qwen3-4b", "qwen3-14b"):
        rows += position_rows(
            chain=0,
            iteration=0,
            held_out=[(1000 + i, 100 * i, 30 + i) for i in range(10)],
            model=model,
        )
        rows += position_rows(chain=0, iteration=1, held_out=[], played=False, model=model)
        rows += position_rows(chain=1, iteration=0, held_out=[], played=True, model=model)
        rows += position_rows(
            chain=1, iteration=1, held_out=[(1000, 500, 55), (1001, 300, 45)], model=model
        )
    curves = build_curves(rows)
    values = plots.held_out_values(rows, "pieces_placed")

    written = [plots.model_figure(curve, values, tmp_path) for curve in curves]
    written.append(plots.ladder_figure(curves, values, tmp_path))
    for path in written:
        assert path.exists()
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
