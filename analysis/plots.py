"""Draw the improvement curves from a loop log.

Milestone 8, the picture half. :mod:`tetris_bench.curves` does the aggregation
and ``analysis/curves.py`` prints it; this file only draws, so a change here can
never change a number. Everything plotted comes from :class:`Curve`, and the
positions singled out on the figures come from :meth:`Curve.unlogged_positions`
and :meth:`Curve.incomplete_positions` rather than from a test repeated here, so
the figures and the table cannot drift apart.

Four things the figures are built to make unmissable, because each is a way a
rising line can be read as learning when it is not.

**The chains are drawn, not just their median.** Chains are independent lineages
that never see each other's functions, and the spread between nominally
equivalent runs is enormous -- three near-identical prompts on one rung gave
held-out 2,540, 120 and 5. A median alone hides exactly that disagreement, so the
per-chain lines are full-strength coloured lines and the band between the best
and worst chain at each iteration is shaded. A rising median drawn over three
agreeing chains is a result; the same median over one chain carrying two
collapsed ones is not.

**Two noise bands, because "the noise" is two different numbers.** The wide band
is :meth:`Curve.delta_noise` -- the bar a change between iterations has to clear,
which is generation noise (chains disagreeing) or seed noise on the plotted mean,
whichever is larger. The narrow band is :meth:`Curve.noise_of_mean` alone: the
seed noise a single-chain log can see. Drawing only the narrow one would invite
calling a gain real when rerunning the model would have produced it anyway;
drawing only the wide one would hide which of the two sources is doing the work.

**A second panel on pieces placed.** ``docs/findings/held-out-seeds.md`` measures
score as separating functions with a between/within variance ratio of 1.10
against 2.07 for pieces placed -- about 1.9x worse -- because score is driven by
rare multi-line clears and has a dead zone: a function that never completes a row
scores exactly 0 however long it survived. Pieces placed is a smooth survival
measure with neither problem, so it is plotted beside the headline score rather
than instead of it.

**A position that did not produce a full held-out set is marked, not smoothed.**
Three cases, three markers: the function was rejected or crashed (a real zero),
the held-out games are missing from the log (a gap that the aggregation scores
zero, which is not the same claim), and the held-out set is short (a real mean,
but a noisier one than its neighbours).

    uv sync --all-extras
    uv run python analysis/plots.py
    uv run python analysis/plots.py --log runs/loop.jsonl --out analysis/figures
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib

# A run on a headless box, or one started from a long sweep, has no display.
# Selecting the file-only backend must happen before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must follow matplotlib.use)

from tetris_bench.curves import Curve, PositionSummary, build_curves  # noqa: E402
from tetris_bench.jsonl import read_records  # noqa: E402

#: Distinct colours for chains. Deliberately a qualitative palette rather than
#: shades of grey: a reader has to be able to follow one lineage across six
#: iterations and see which chain collapsed, which grey-on-grey does not allow.
CHAIN_COLOURS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf")
MEDIAN_COLOUR = "#111111"
MODEL_COLOURS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf")

#: Held-out values of one field, keyed by ``(model, chain, iteration)``.
PositionValues = dict[tuple[str, int, int], list[float]]

#: How to read one measure off a position. ``None`` means "no value here", which
#: is drawn as a gap rather than as a zero.
Reader = Callable[[PositionSummary], float | None]


@dataclass(frozen=True)
class Panel:
    """One measure of one model, ready to draw.

    ``per_chain`` and ``median`` hold ``None`` where there is no value, so a
    chain cut short by an interrupted run draws as a line that stops rather than
    one that silently continues at someone else's value.
    """

    label: str
    median: list[float | None]
    per_chain: dict[int, list[float | None]]
    #: The bar a change between iterations has to clear (generation noise, or
    #: seed noise on the plotted mean, whichever is larger).
    delta_noise: float
    #: Seed noise on the plotted mean alone, which is the smaller, more
    #: optimistic of the two sources.
    mean_noise: float
    #: Held-out games behind a full position, for the labels.
    games: int
    #: ``(chain, iteration)`` of positions the function never played.
    rejected: list[tuple[int, int]]
    #: ``(chain, iteration)`` of positions whose held-out games are missing.
    unlogged: list[tuple[int, int]]
    #: ``(chain, iteration, games)`` of positions with a short held-out set.
    under_sampled: list[tuple[int, int, int]]


def score_of(position: PositionSummary) -> float | None:
    """The curve's headline measure: points per piece. Always a number, zero included.

    Reads `headline` rather than `eval_score` so the figure and the table in
    `analysis/curves.py` cannot disagree about what is being plotted. That is a
    tested invariant, and it caught this exact drift when the headline moved
    from totals to rates.
    """
    return position.headline


def pieces_of(position: PositionSummary) -> float | None:
    """Pieces placed, with the two kinds of missing value kept apart.

    ``eval_pieces`` is ``None`` whenever no held-out game was logged, which
    covers two different facts. A **rejected** function never played, so it
    placed no pieces on the held-out sequences: that is a real zero, the same one
    its score carries, and dropping it would flatter the model. A position whose
    held-out games are simply **absent from the log** has no value at all, and
    imputing a zero there would invent the worst possible result out of a gap in
    the log. Note this is why holes is not plotted: a zero hole count reads as a
    flawless board, so there is no honest imputation for it.
    """
    if position.eval_pieces is not None:
        return position.eval_pieces
    return 0.0 if position.rejected else None


def held_out_values(rows: Iterable[dict], field: str) -> PositionValues:
    """Per position, one field's values over the held-out games only.

    Needed because :class:`Curve` carries its noise statistics for score and not
    for pieces placed. Same filter as the aggregation: strategy mode,
    ``split == "eval"``.
    """
    collected: PositionValues = {}
    for row in rows:
        if row.get("mode") != "strategy" or row.get("split") != "eval":
            continue
        key = (str(row.get("model", "")), int(row.get("chain", 0)), int(row.get("iteration", 0)))
        collected.setdefault(key, []).append(float(row[field]))
    return collected


def pieces_noise(curve: Curve, values: PositionValues) -> tuple[float, float]:
    """``(delta_noise, noise_of_mean)`` for pieces placed.

    A mirror of :meth:`Curve.delta_noise` and :meth:`Curve.noise_of_mean` for the
    one measure ``curves.py`` does not carry statistics for. The definitions are
    deliberately the same: median within-position spread, divided by root-n for
    the spread of the plotted mean, against the median between-chain spread for
    generation noise, with the larger of the two as the bar. If ``curves.py``
    ever grows a measure-agnostic version, delete this and call it.
    """
    per_position = [
        (key, sample) for key, sample in values.items() if key[0] == curve.model and len(sample) > 1
    ]
    if not per_position:
        return (0.0, 0.0)

    seed = statistics.median([statistics.stdev(sample) for _, sample in per_position])
    games = statistics.median([len(sample) for _, sample in per_position])
    mean_noise = seed / math.sqrt(games) if games > 1 else seed

    # Generation noise: how far apart independent chains sit at one iteration.
    spreads: list[float] = []
    for iteration in curve.iterations:
        at = [
            value
            for value in (pieces_of(p) for p in curve.positions if p.iteration == iteration)
            if value is not None
        ]
        if len(at) > 1:
            spread = statistics.stdev(at)
            if spread > 0.0:
                spreads.append(spread)
    chain_spread = statistics.median(spreads) if spreads else 0.0

    return (max(chain_spread, mean_noise), mean_noise)


def build_panel(
    curve: Curve,
    *,
    label: str,
    value: Reader,
    delta_noise: float,
    mean_noise: float,
) -> Panel:
    """Collect one measure for one model across its chains and iterations.

    The median is taken across chains at each iteration over the values that
    exist, matching :meth:`Curve.median_score` for score. The positions worth
    marking are taken from the :class:`Curve` itself, so the figure and the
    printed table always single out the same positions.
    """
    iterations = curve.iterations
    by_position = {(p.chain, p.iteration): p for p in curve.positions}

    median: list[float | None] = []
    for iteration in iterations:
        at = [v for v in (value(p) for p in curve.positions if p.iteration == iteration)]
        present = [v for v in at if v is not None]
        median.append(statistics.median(present) if present else None)

    per_chain: dict[int, list[float | None]] = {}
    for chain in curve.chains:
        per_chain[chain] = [
            value(by_position[(chain, i)]) if (chain, i) in by_position else None
            for i in iterations
        ]

    unlogged = curve.unlogged_positions()
    return Panel(
        label=label,
        median=median,
        per_chain=per_chain,
        delta_noise=delta_noise,
        mean_noise=mean_noise,
        games=max((p.eval_games for p in curve.positions), default=0),
        rejected=sorted((p.chain, p.iteration) for p in unlogged if p.rejected),
        unlogged=sorted((p.chain, p.iteration) for p in unlogged if not p.rejected),
        under_sampled=sorted(
            (p.chain, p.iteration, p.eval_games) for p in curve.incomplete_positions()
        ),
    )


def panels_for(curve: Curve, pieces_values: PositionValues) -> tuple[Panel, Panel]:
    """The two panels of a model's figure: score, then pieces placed."""
    pieces_delta, pieces_mean = pieces_noise(curve, pieces_values)
    score = build_panel(
        curve,
        label="held-out points per piece",
        value=score_of,
        delta_noise=curve.delta_noise(),
        mean_noise=curve.noise_of_mean(),
    )
    pieces = build_panel(
        curve,
        label="held-out pieces placed",
        value=pieces_of,
        delta_noise=pieces_delta,
        mean_noise=pieces_mean,
    )
    return score, pieces


def draw_noise_bands(axis: plt.Axes, panel: Panel, iterations: Sequence[int]) -> None:
    """Shade both noise scales around the first iteration's median.

    Centred on iteration 0 rather than on each point: the question the figure has
    to answer is whether the *gain* escaped the noise, so the band is the region a
    later median has to leave before the change means anything.
    """
    start = next((value for value in panel.median if value is not None), None)
    if start is None:
        return
    left, right = min(iterations), max(iterations)

    bands = (
        (
            panel.delta_noise,
            "#9e9e9e",
            0.18,
            f"bar for a real change (±{panel.delta_noise:,.1f}, generation + seed)",
        ),
        (
            panel.mean_noise,
            "#616161",
            0.22,
            f"seed noise on the plotted mean (±{panel.mean_noise:,.1f}, n={panel.games})",
        ),
    )
    for width, colour, alpha, label in bands:
        if width <= 0:
            continue
        axis.fill_between(
            [left, right],
            [start - width] * 2,
            [start + width] * 2,
            color=colour,
            alpha=alpha,
            zorder=0,
            label=label,
        )


def draw_panel(axis: plt.Axes, panel: Panel, iterations: Sequence[int]) -> None:
    """One measure: chain lines, the disagreement band, and the median over them."""
    draw_noise_bands(axis, panel, iterations)

    # The best-to-worst band across chains at each iteration. This is generation
    # noise shown directly: a median drawn over a wide band is a median of
    # lineages that disagree, and the project has measured that disagreement to
    # be larger than everything else in the figure.
    columns = [
        [v for v in (panel.per_chain[c][i] for c in panel.per_chain) if v is not None]
        for i, _ in enumerate(iterations)
    ]
    if any(len(column) > 1 for column in columns):
        # NaN rather than None for the gaps: matplotlib skips a NaN, while a
        # None in a fill_between array makes the whole array a Python object
        # array and the call fails.
        axis.fill_between(
            iterations,
            [min(column) if column else math.nan for column in columns],
            [max(column) if column else math.nan for column in columns],
            color="#1f77b4",
            alpha=0.10,
            zorder=1,
            label="chain spread (best to worst)",
        )

    for index, (chain, series) in enumerate(sorted(panel.per_chain.items())):
        axis.plot(
            iterations,
            series,
            color=CHAIN_COLOURS[index % len(CHAIN_COLOURS)],
            linewidth=1.5,
            marker="o",
            markersize=4.5,
            alpha=0.9,
            zorder=2,
            label=f"chain {chain}",
        )

    axis.plot(
        iterations,
        panel.median,
        color=MEDIAN_COLOUR,
        linewidth=2.8,
        marker="s",
        markersize=6,
        zorder=3,
        label=f"median of {len(panel.per_chain)} chain(s)",
    )

    draw_flags(axis, panel, iterations)

    axis.set_xlabel("iteration")
    axis.set_ylabel(panel.label)
    axis.set_xticks(list(iterations))
    axis.grid(alpha=0.25, linewidth=0.6)
    # Neither measure can be negative, so the part of a noise band that falls
    # below zero is an artefact of drawing a symmetric band, not a possible
    # value. The small margin below zero is only so that a marker sitting at zero
    # is not sliced in half by the axis.
    axis.set_ylim(bottom=-0.035 * axis.get_ylim()[1])
    _legend_without_duplicates(axis)


def draw_flags(axis: plt.Axes, panel: Panel, iterations: Sequence[int]) -> None:
    """Mark the positions that are not an ordinary held-out mean.

    Three distinct marks, because they are three distinct claims: a function that
    failed, a gap in the log that the aggregation scores as zero, and a mean over
    fewer games than its neighbours.
    """
    for _chain, iteration in panel.rejected:
        axis.scatter(
            [iteration],
            [0.0],
            marker="X",
            s=130,
            color="#b71c1c",
            zorder=4,
            label="function rejected or crashed (a real 0)",
        )
    for _chain, iteration in panel.unlogged:
        axis.scatter(
            [iteration],
            [0.0],
            marker="P",
            s=130,
            color="#ef6c00",
            zorder=4,
            label="held-out games missing from the log (scored 0)",
        )

    # An under-sampled position is a real measurement, so it keeps its point on
    # the line; the ring says only that this point is noisier than its
    # neighbours, by about root(full/short).
    index_of = {iteration: index for index, iteration in enumerate(iterations)}
    for chain, iteration, games in panel.under_sampled:
        value = panel.per_chain.get(chain, [])[index_of[iteration]]
        if value is None:
            continue
        axis.scatter(
            [iteration],
            [value],
            marker="o",
            s=170,
            facecolors="none",
            edgecolors="#6a1b9a",
            linewidths=1.8,
            zorder=4,
            label=f"short held-out set (n<{panel.games}, here {games})",
        )


def _legend_without_duplicates(axis: plt.Axes) -> None:
    """One entry per label: a flag marker is drawn once per flagged position."""
    handles, labels = axis.get_legend_handles_labels()
    unique: dict[str, object] = {}
    for handle, label in zip(handles, labels, strict=True):
        unique.setdefault(label, handle)
    # Below the axes, not inside them. Every in-axes placement, "best" included,
    # put the box over data at some point while developing this -- once directly
    # on top of a flagged zero, which is the single mark the figure exists to
    # show. Outside the axes it cannot hide anything.
    axis.legend(
        unique.values(),
        unique.keys(),
        fontsize=7.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=2,
        framealpha=0.9,
    )


def median_abs_delta(curve: Curve) -> float:
    """How far a typical revision moves the score, in either direction.

    The companion to :meth:`Curve.mean_delta`, which telescopes: the mean of a
    chain's within-chain deltas *is* its first-to-last difference divided by the
    number of steps, so every intermediate rise and fall cancels. A chain that
    went 100 → 2,000 → 5 → 400 and one that climbed smoothly to 400 report the
    same mean delta. This says how big the steps were, and the two together say
    whether the net is a trend or a cancellation.
    """
    deltas = [abs(delta) for _, _, delta in curve.paired_deltas()]
    return statistics.median(deltas) if deltas else 0.0


def model_figure(curve: Curve, pieces_values: PositionValues, out_dir: Path) -> Path:
    """One model: score and pieces placed side by side. Returns the saved path."""
    score, pieces = panels_for(curve, pieces_values)
    iterations = curve.iterations

    figure, axes = plt.subplots(1, 2, figsize=(13.5, 6.4))
    draw_panel(axes[0], score, iterations)
    draw_panel(axes[1], pieces, iterations)

    gained = curve.score_gained()
    medians = [value for value in score.median if value is not None]
    peak = max(medians) if medians else 0.0
    # In multiples of the bar, not "bigger than the bar". A threshold crossing
    # printed as a verdict loses how marginal it was, and a flat arm built with
    # no trend at all crossed this one at 1.7x while its chains were visibly
    # bouncing. The multiple is a measured quantity; "larger than the noise" is
    # a derived flag.
    margin = f", {gained / score.delta_noise:.1f}x the bar" if score.delta_noise > 0 else ""
    figure.suptitle(
        f"{curve.model} — held-out improvement over {len(iterations)} iteration(s), "
        f"{len(curve.chains)} chain(s), up to {score.games} held-out seeds per position\n"
        # The peak is named beside the first-to-last gain on purpose: a signed
        # difference between two endpoints says nothing about the shape between
        # them, and a curve that peaked and fell back reads as flat without it.
        f"median pts/piece {medians[0] if medians else 0:,.1f} → "
        f"{medians[-1] if medians else 0:,.0f} ({gained:+,.0f}{margin}), peak {peak:,.0f}; "
        f"{curve.regressions()} of {len(curve.paired_deltas())} within-chain steps regressed, "
        f"median |step| {median_abs_delta(curve):,.0f}",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.02, 1, 0.94))

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"curve-{curve.model}.png"
    figure.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(figure)
    return path


def ladder_order(curve: Curve) -> tuple[float, str]:
    """Sort key putting the rungs in size order: 4b, 14b, 30b, not alphabetical.

    The size is read out of the model name, which is a convention rather than a
    fact, so a name it cannot read sorts last by name instead of guessing.
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", curve.model.lower())
    return (float(match.group(1)) if match else float("inf"), curve.model)


def _ladder_bars(curves: Sequence[Curve], pieces_values: PositionValues, out_dir: Path) -> Path:
    """The ladder as bars, for a run with one iteration per model.

    Same numbers as the line version, but a comparison across models rather
    than a curve through time, because there is no time axis to draw.
    """
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    names = [c.model for c in curves]
    colours = [MODEL_COLOURS[i % len(MODEL_COLOURS)] for i in range(len(curves))]
    series = [panels_for(c, pieces_values) for c in curves]

    labels = ("median held-out points per piece", "median held-out pieces")
    for axis, which, label in ((axes[0], 0, labels[0]), (axes[1], 1, labels[1])):
        values = [
            (s[which].median[0] if s[which].median and s[which].median[0] is not None else 0.0)
            for s in series
        ]
        bars = axis.bar(names, values, color=colours, width=0.6)
        axis.bar_label(bars, fmt="%.1f" if which == 0 else "%.0f", fontsize=9, padding=2)
        axis.set_ylabel(label)
        axis.grid(alpha=0.25, linewidth=0.6, axis="y")
        axis.set_ylim(bottom=0, top=max(values) * 1.18 if any(values) else 1.0)
        axis.tick_params(axis="x", labelrotation=15)

    figure.suptitle(
        "The ladder — one generation per chain, 15 chains per rung, no feedback\n"
        "median over all 15 positions, a rejected function counting as a zero",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.02, 1, 0.9))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ladder.png"
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def ladder_figure(curves: Sequence[Curve], pieces_values: PositionValues, out_dir: Path) -> Path:
    """Every model on one axis: the capability-ladder comparison.

    Medians only, with each model's :meth:`Curve.delta_noise` as a ribbon -- the
    spread a rerun of the same request would produce, which is the right scale
    for asking whether two rungs differ. The per-chain detail lives in the
    per-model figures; six chains per model on one axis would make neither
    readable.
    """
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    ordered = sorted(curves, key=ladder_order)

    # A ladder measured at iteration 0 only -- which is how the published one
    # was run -- has a single point per model. Drawn as a line that is four dots
    # stacked on a degenerate x-axis from -0.04 to 0.04, which is technically
    # the data and useless as a chart. Bars are what one value per model wants.
    single = max((len(c.iterations) for c in ordered), default=0) <= 1
    if single:
        return _ladder_bars(ordered, pieces_values, out_dir)

    for index, curve in enumerate(ordered):
        colour = MODEL_COLOURS[index % len(MODEL_COLOURS)]
        iterations = curve.iterations
        for axis, panel in zip(axes, panels_for(curve, pieces_values), strict=True):
            axis.plot(
                iterations,
                panel.median,
                color=colour,
                linewidth=2.2,
                marker="o",
                markersize=5,
                label=f"{curve.model} (n={panel.games})",
            )
            band = panel.delta_noise
            axis.fill_between(
                iterations,
                [math.nan if value is None else value - band for value in panel.median],
                [math.nan if value is None else value + band for value in panel.median],
                color=colour,
                alpha=0.14,
            )

    labels = ("median held-out points per piece", "median held-out pieces")
    for axis, label in ((axes[0], labels[0]), (axes[1], labels[1])):
        axis.set_xlabel("iteration")
        axis.set_ylabel(label)
        axis.grid(alpha=0.25, linewidth=0.6)
        axis.set_ylim(bottom=0)
        axis.legend(fontsize=8, loc="best", framealpha=0.9)

    figure.suptitle(
        "The ladder — median held-out curve per model, ribbon = the bar a change must clear\n"
        "pieces placed separates functions about 1.9x better than score "
        "(docs/findings/held-out-seeds.md)",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.02, 1, 0.92))

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ladder.png"
    figure.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(figure)
    return path


def report_gaps(curve: Curve) -> None:
    """Say out loud what a figure can only mark.

    A marker says *that* a point is unusual; these lines say which position and
    how short, which is what you need to go and look at the log.
    """
    for position in curve.unlogged_positions():
        if position.rejected:
            continue
        print(
            f"  note: chain {position.chain} iteration {position.iteration} played its "
            f"training seeds but logged no held-out games; it is plotted as a zero, "
            f"which is missing data rather than a bad function"
        )
    for position in curve.incomplete_positions():
        print(
            f"  note: chain {position.chain} iteration {position.iteration} has only "
            f"{position.eval_games} held-out games; its mean is real but noisier than "
            f"the rest of the curve"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the improvement curves from a loop log.")
    parser.add_argument("--log", type=Path, default=Path("runs/loop.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("analysis/figures"))
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="only this model (repeatable); default is every model in the log",
    )
    args = parser.parse_args()

    if not args.log.exists():
        raise SystemExit(
            f"no log at {args.log}. Run the loop first:\n"
            f"  uv run tetris-bench loop --model qwen3-14b --iterations 6"
        )

    rows = list(read_records(args.log))
    curves = [c for c in build_curves(rows) if args.model is None or c.model in args.model]
    if not curves:
        raise SystemExit(f"{args.log} holds no strategy-mode rows, so there is no curve to draw.")

    # One pass over the log for the pieces spreads, shared by every figure.
    pieces_values = held_out_values(rows, "pieces_placed")

    for curve in curves:
        print(f"wrote {model_figure(curve, pieces_values, args.out)}")
        report_gaps(curve)

    if len(curves) > 1:
        print(f"wrote {ladder_figure(curves, pieces_values, args.out)}")


if __name__ == "__main__":
    main()
