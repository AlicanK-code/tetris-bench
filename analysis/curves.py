"""Print the improvement curves from a loop log.

Milestone 8. The aggregation itself lives in :mod:`tetris_bench.curves`, which is
pure and unit-tested; this file is only presentation, so a change to how a number
is displayed can never change the number.

Every score printed here is a **held-out** mean over evaluation seeds the model
was never shown. The training column is printed beside it on purpose: the gap
between the two is how far a revision was tuned to the sequences it saw, and this
project has already recorded a training score of 400 whose held-out value was
110. Both columns are medians across chains, so that gap is not partly an
artefact of comparing a mean with a median.

    uv run python analysis/curves.py
    uv run python analysis/curves.py --log runs/loop.jsonl --tolerance 150
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from tetris_bench.curves import Curve, PositionSummary, build_curves
from tetris_bench.jsonl import read_records


def thousands(value: float) -> str:
    return f"{value:,.0f}"


def optional_mean(values: list[float | None], places: int, width: int) -> str:
    """Average the positions that have a board, or ``--`` when none does.

    ``eval_pieces`` and ``eval_holes`` are ``None`` for a position that logged
    no held-out game. Treating those as zero would enter a non-existent board
    into the average as a flawless one — zero holes is the best possible value.
    """
    present = [v for v in values if v is not None]
    if not present:
        return f"{'--':>{width}}"
    return f"{statistics.fmean(present):>{width}.{places}f}"


def print_curve(curve: Curve, tolerance: float | None) -> None:
    chains = curve.chains
    counts = sorted({p.eval_games for p in curve.positions})
    print(f"\n{'=' * 86}")
    print(
        f"{curve.model}  -  {len(chains)} chain(s) x {len(curve.iterations)} iteration(s), "
        f"held-out games per position: {counts if len(counts) > 1 else counts[0] if counts else 0}"
    )
    print("=" * 86)

    # Units are spelled out because two of these columns are rates and three
    # are totals, and the headline moved from the second kind to the first.
    header = (
        f"{'iter':>4} {'pts/pc':>7} {'score':>8} {'med':>8} {'chains':>7} {'n':>3} "
        f"{'train':>8} {'pieces':>7} {'holes':>6} {'tokens':>8} {'secs':>7}  "
        f"per-chain pts/pc"
    )
    print(header)
    print("-" * len(header))

    # Computed once rather than per row: median_score walks every position.
    medians = curve.median_score()
    for index, iteration in enumerate(curve.iterations):
        at = sorted((p for p in curve.positions if p.iteration == iteration), key=lambda p: p.chain)
        # The headline, so this row and the `pts/pc` column cannot disagree.
        per_chain = ", ".join(f"{p.headline:,.1f}{marker(p)}" for p in at)

        # Spread *between chains* at this iteration — generation noise, which the
        # project has measured to dominate seed noise. The previous column was a
        # maximum of the within-position single-game sd, a statistic used nowhere
        # else and never compared against anything.
        # In headline units, so it is comparable with the noise bar printed
        # below it. A spread of totals against a threshold on rates would be a
        # unit error of about the piece count.
        spread = statistics.stdev([p.headline for p in at]) if len(at) > 1 else 0.0
        games = sorted({p.eval_games for p in at})

        print(
            f"{iteration:>4} {medians[index]:>7,.1f} "
            f"{statistics.median([p.eval_score for p in at]):>8,.0f} "
            f"{statistics.median([p.eval_median for p in at]):>8,.0f} {spread:>7,.1f} "
            f"{(str(games[0]) if len(games) == 1 else 'mix'):>3} "
            f"{statistics.median([p.train_score for p in at]):>8,.0f} "
            f"{optional_mean([p.eval_pieces for p in at], 1, 7)} "
            f"{optional_mean([p.eval_holes for p in at], 1, 6)} "
            f"{thousands(sum(p.tokens for p in at)):>8} "
            f"{sum(p.seconds for p in at):>7.0f}  {per_chain}"
        )

    print_flags(curve)
    print_summary(curve, tolerance)


def marker(position: PositionSummary) -> str:
    """Why a position scored zero, when it did.

    Chosen on the measured ``eval_games``, not on the ``rejected`` flag: a
    position can have `played=True` training rows and no held-out rows at all —
    a crash on the first evaluation sequence, or a run killed between the two
    writes. That is a gap in the log rather than a result, and it must not read
    as an ordinary zero.
    """
    if position.eval_games:
        return ""
    return "*" if position.rejected else "?"


def print_flags(curve: Curve) -> None:
    rejected = [p for p in curve.unlogged_positions() if p.rejected]
    unlogged = [p for p in curve.unlogged_positions() if not p.rejected]
    incomplete = curve.incomplete_positions()

    if rejected:
        print("\n  * the function was rejected or crashed, so no game ran; it scores zero")
    if unlogged:
        where = ", ".join(f"chain {p.chain} iter {p.iteration}" for p in unlogged)
        print(
            f"\n  ? NO held-out game was logged ({where}). This is a gap in the log,"
            "\n    not a measured zero. Re-run the loop: it replays the saved function"
            "\n    and fills the missing games without a model call."
        )
    if incomplete:
        where = ", ".join(
            f"chain {p.chain} iter {p.iteration} ({p.eval_games} games)" for p in incomplete
        )
        print(
            f"\n  ! under-sampled positions: {where}."
            "\n    Their means are pooled with fuller ones in the same median."
        )


def print_summary(curve: Curve, tolerance: float | None) -> None:
    bar = curve.delta_noise()
    used = bar if tolerance is None else tolerance
    gained = curve.score_gained()
    medians = curve.median_score()

    def row(label: str, value: str) -> None:
        print(f"  {label:<44} : {value}")

    # "undefined" rather than a number, because a flat or falling curve has no
    # cost per point, and a placeholder figure in a results table reads as
    # though it were comparable with a real one.
    def per_point(value: float | None, places: int) -> str:
        if value is None:
            return "undefined (no chain gained more than the noise)"
        return f"{value:,.{places}f}"

    low, high = curve.chain_spread_range()
    steps = len(curve.paired_deltas())
    qualifying = curve.qualifying_chains()

    print()
    row("seed noise, one held-out game", f"{curve.seed_noise():,.0f}")
    row("seed noise on the plotted mean", f"{curve.noise_of_mean():,.0f}")
    row(
        "generation noise, between chains",
        f"{curve.chain_spread():,.0f}  (per iteration: {low:,.0f} to {high:,.0f})",
    )
    row("--> bar for a real change", f"{bar:,.0f}")
    # The mean is a telescoping sum, so it is printed as what it is and the
    # typical step size is printed beside it. Without that, "+3 per revision"
    # hides revisions that routinely move the score five times further.
    row(
        "net delta per revision (= first-to-last / steps)",
        f"{curve.mean_delta():+,.0f}",
    )
    row("typical step size, any direction", f"{curve.median_abs_delta():,.0f}")
    row(
        "regressions",
        f"{curve.regressions()} of {steps} steps fell; "
        f"{curve.regressions_beyond(bar)} by more than the bar",
    )
    source = "measured" if tolerance is None else "given"
    row(
        f"plateau, i.e. peak (tolerance {used:,.0f}, {source})",
        f"iteration {curve.plateau_iteration(used)}",
    )
    if medians:
        row("held-out, first to last", f"{medians[0]:,.0f} -> {medians[-1]:,.0f} ({gained:+,.0f})")
        row("held-out peak", f"{max(medians):,.0f}")
        row("fall from peak", f"{curve.fall_from_peak():,.0f}")
    row("total cost", f"{thousands(curve.total_tokens())} tokens, {curve.total_seconds():,.0f}s")
    row(
        "tokens per point, per chain",
        f"{per_point(curve.tokens_per_point(), 1)}"
        f"  ({len(qualifying)} of {len(curve.chains)} chains qualified)",
    )
    row("seconds per point, per chain", per_point(curve.seconds_per_point(), 2))

    # The headline the project is for. Reported as a *margin*, not a threshold
    # crossing: "larger than the noise" reads identically at 1.1x and at 11x,
    # and a flat arm generated with no trend at all crossed it at 1.7x.
    if used <= 0:
        print("\n  no noise estimate available, so no verdict: this log has one chain")
        print("  and one held-out game per position.")
    elif gained > 0:
        multiple = gained / used
        if multiple >= 2.0:
            print(f"\n  gain {gained:+,.0f}, which is {multiple:.1f}x the noise bar of {used:,.0f}")
        else:
            print(
                f"\n  gain {gained:+,.0f}, only {multiple:.1f}x the noise bar of {used:,.0f}"
                " - treat as indistinguishable from noise"
            )
        print("  (a ladder of several rungs gives several chances to cross a bar,")
        print("  so read a bare crossing on one rung with suspicion)")
    else:
        print(f"\n  no held-out gain ({gained:+,.0f}), against a noise bar of {used:,.0f}")
    if curve.fall_from_peak() > used:
        print(
            f"  NOTE: it fell {curve.fall_from_peak():,.0f} from its peak, more than the"
            f" bar - it got worse after its best iteration."
        )
    if len(curve.chains) < 2:
        print("  NOTE: one chain cannot see generation noise, so the bar above is")
        print("  known to be too lenient. Run several chains before trusting a gain.")


def print_ladder(curves: list[Curve]) -> None:
    """The capability-ladder table, ready to paste into the README."""
    if len(curves) < 2:
        return
    print(f"\n{'=' * 86}")
    print("The ladder")
    print("=" * 86)
    print("| model | iter 0 | final | peak | gain | bar | regressions | tokens/pt | secs/pt |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for curve in curves:
        medians = curve.median_score()
        if not medians:
            continue
        tokens_per = curve.tokens_per_point()
        seconds_per = curve.seconds_per_point()
        print(
            f"| `{curve.model}` | {medians[0]:,.0f} | {medians[-1]:,.0f} "
            f"| {max(medians):,.0f} | {curve.score_gained():+,.0f} "
            f"| {curve.delta_noise():,.0f} "
            f"| {curve.regressions()}/{len(curve.paired_deltas())} "
            f"| {f'{tokens_per:,.0f}' if tokens_per is not None else '--'} "
            f"| {f'{seconds_per:,.2f}' if seconds_per is not None else '--'} |"
        )
    print("\n`bar` is the noise a gain has to clear: generation noise between chains")
    print("where there are several, else seed noise on the mean. Cost per point is")
    print("per chain, so it does not scale with how many chains a rung was run at.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("runs/loop.jsonl"))
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="plateau threshold in points; defaults to the log's own measured noise",
    )
    args = parser.parse_args()

    if not args.log.exists():
        raise SystemExit(
            f"no log at {args.log}. Run the loop first:\n"
            f"  uv run tetris-bench loop --model qwen3-14b --iterations 6 --chains 3"
        )

    curves = build_curves(read_records(args.log))
    if not curves:
        raise SystemExit(f"{args.log} holds no strategy-mode rows, so there is no curve to draw.")

    for curve in curves:
        print_curve(curve, args.tolerance)
    print_ladder(curves)
    print()


if __name__ == "__main__":
    main()
