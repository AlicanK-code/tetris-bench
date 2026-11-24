"""How many decisions did each revision actually change? Presentation only.

The comparison, the pairing and the one-sided design all live in
:mod:`tetris_bench.placement_diff`, which is unit-tested, so a change to how
this prints cannot change what it concludes. Read that module's docstring first:
the measure is deliberately asymmetric and the rate is a floor, not an effect
size.

This exists because the published inertness figure -- 8 of 90 live revisions
scoring identically on every held-out sequence -- counts **exact ties in the
totals**, and so misses a revision that changes one decision in a thousand or
that changes several and lands on the same total anyway. Here the unit is the
decision.

    uv run python analysis/placement_diff.py
    uv run python analysis/placement_diff.py --runs 8b-loop --seeds 1000 1001
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import time
from pathlib import Path

from tetris_bench.placement_diff import PairDiff, diff_pair, lineage_pairs
from tetris_bench.zeros_rate import is_dead

PUBLISHED = Path("runs/published")
DEFAULT_RUNS = ("4b-loop", "8b-loop", "five-chain", "30b-pilot", "clean-6iter")
EVAL_SEEDS = tuple(range(1000, 1010))

#: Below this share of decisions a revision is reported as near-inert. Chosen as
#: one decision in two hundred, which on these game lengths is one or two moves
#: in ten games -- small enough that the score difference it produces is a
#: property of those moves rather than of the strategy.
NEAR_INERT = 0.005


def held_out_rate(rows: list[dict]) -> dict[tuple[str, int, int], float]:
    """Points per piece on the evaluation split, per position."""
    totals: dict[tuple[str, int, int], list[int]] = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row.get("split") == "eval":
            key = (row["model"], row["chain"], row["iteration"])
            totals[key][0] += row["score"]
            totals[key][1] += row["pieces_placed"]
    return {key: score / pieces for key, (score, pieces) in totals.items() if pieces}


def exact_ties(rows: list[dict]) -> set[tuple[str, int, int]]:
    """Positions whose totals matched the next iteration's exactly, per key A.

    The published test, recomputed here so the two can be cross-tabulated rather
    than compared across documents.
    """
    totals: dict[tuple[str, int, int], list[int]] = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row.get("split") == "eval":
            key = (row["model"], row["chain"], row["iteration"])
            totals[key][0] += row["score"]
            totals[key][1] += row["pieces_placed"]
    out = set()
    for (model, chain, iteration), value in totals.items():
        nxt = totals.get((model, chain, iteration + 1))
        if nxt is not None and value == nxt and value[1] > 0:
            out.add((model, chain, iteration))
    return out


def describe(diff: PairDiff, dead: bool, tied: bool) -> str:
    if diff.failure:
        return f"  {diff.label:<40} FAILED  {diff.failure[:60]}"
    flags = "".join(("D" if dead else " ", "=" if tied else " "))
    verdict = (
        "INERT"
        if diff.inert
        else ("near-inert" if diff.rate < NEAR_INERT else f"{100 * diff.rate:.1f}%")
    )
    first = "-" if diff.first_divergence is None else str(diff.first_divergence)
    return (
        f"  {diff.label:<40} {flags}  {diff.moves:>6} decisions  "
        f"{diff.diverged:>5} changed  first at {first:>6}  {verdict}"
    )


def run_one(run: str, seeds: tuple[int, ...], max_pieces: int) -> list[tuple[PairDiff, bool, bool]]:
    rows = [json.loads(line) for line in (PUBLISHED / run / "loop.jsonl").open()]
    functions = PUBLISHED / run / "functions"
    rates = held_out_rate(rows)
    tied = exact_ties(rows)

    results = []
    for pair in lineage_pairs(rows):
        source_a = functions / f"{pair.name_a}.py"
        source_b = functions / f"{pair.name_b}.py"
        if not (source_a.exists() and source_b.exists()):
            continue
        rate_a = rates.get((pair.model, pair.chain, pair.iteration_a))
        rate_b = rates.get((pair.model, pair.chain, pair.iteration_b))
        dead = rate_a is None or rate_b is None or is_dead(rate_a) or is_dead(rate_b)
        diff = diff_pair(
            pair.label,
            source_a.read_text(),
            source_b.read_text(),
            seeds=seeds,
            max_pieces=max_pieces,
        )
        results.append((diff, dead, (pair.model, pair.chain, pair.iteration_a) in tied))
        print(describe(diff, dead, (pair.model, pair.chain, pair.iteration_a) in tied), flush=True)
    return results


def summarise(label: str, rows: list[tuple[PairDiff, bool, bool]]) -> None:
    usable = [(d, dead, tie) for d, dead, tie in rows if not d.failure and d.moves]
    if not usable:
        print(f"\n{label}: nothing comparable")
        return
    live = [(d, tie) for d, dead, tie in usable if not dead]
    inert = [d for d, _ in live if d.inert]
    near = [d for d, _ in live if not d.inert and d.rate < NEAR_INERT]
    tied_live = [d for d, tie in live if tie]

    print(f"\n{label}")
    print(f"  revisions compared              : {len(usable)} ({len(live)} between live functions)")
    print(f"  changed no decision at all      : {len(inert)} of {len(live)} live")
    print(f"  changed fewer than 1 in 200     : {len(near)} more")
    print(f"  scored identically on the totals: {len(tied_live)} (the published test)")
    if live:
        rates = sorted(d.rate for d, _ in live)
        print(
            f"  decisions changed, median       : {100 * statistics.median(rates):.1f}%"
            f"  (range {100 * rates[0]:.1f}% to {100 * rates[-1]:.1f}%)"
        )
    failed = [d for d, _, _ in rows if d.failure]
    if failed:
        print(f"  pairs that could not be played  : {len(failed)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", default=list(DEFAULT_RUNS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(EVAL_SEEDS))
    parser.add_argument("--max-pieces", type=int, default=2000)
    args = parser.parse_args()

    print("Decisions changed per revision, driving each game with the EARLIER function.")
    print("Flags: D = one side is at or below the random ceiling, = = totals matched exactly.\n")

    everything: list[tuple[PairDiff, bool, bool]] = []
    started = time.monotonic()
    for run in args.runs:
        print(f"{run}:")
        rows = run_one(run, tuple(args.seeds), args.max_pieces)
        summarise(run, rows)
        everything.extend(rows)
        print()

    summarise("POOLED", everything)
    print(f"\n{time.monotonic() - started:.0f}s, no model calls.")


if __name__ == "__main__":
    main()
