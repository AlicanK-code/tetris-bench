"""Does the loop rescue dead functions? Presentation only.

The classification, the pairing and the test live in
:mod:`tetris_bench.zeros_rate`, which is pure and unit-tested, so a change to
how this prints cannot change what it concludes.

    uv run python analysis/zeros_rate.py
    uv run python analysis/zeros_rate.py --runs 4b-loop five-chain
    uv run python analysis/zeros_rate.py --measure-floor
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from tetris_bench.curves import build_curves
from tetris_bench.zeros_rate import (
    RANDOM_CEILING,
    chains_needed,
    count_transitions,
    is_dead,
)

PUBLISHED = Path("runs/published")
DEFAULT_RUNS = ("4b-loop", "five-chain")


def series_for(run: str) -> dict[tuple[str, int], list[float]]:
    """Per-chain lists of held-out rates, keyed by (model, chain)."""
    rows = [json.loads(line) for line in (PUBLISHED / run / "loop.jsonl").open()]
    out: dict[tuple[str, int], list[float]] = {}
    for curve in build_curves(rows):
        for chain in curve.chains:
            out[(curve.model, chain)] = [p.headline for p in curve.chain_series(chain)]
    return out


def measure_floor(agent_seeds: int = 20) -> None:
    """Re-measure the random ceiling the 'dead' line is drawn at."""
    from tetris_bench.agents.random_agent import RandomAgent
    from tetris_bench.engine.game import Game
    from tetris_bench.runner import play_game

    seeds = range(1000, 1010)
    rates = []
    total_score = total_pieces = 0
    for agent_seed in range(agent_seeds):
        score = pieces = 0
        for seed in seeds:
            result = play_game(Game(seed=seed, max_pieces=2000), RandomAgent(seed=agent_seed))
            score += result.score
            pieces += result.pieces_placed
        rates.append(score / pieces)
        total_score += score
        total_pieces += pieces
    rates.sort()
    print(f"random over {agent_seeds} agent seeds x 10 evaluation sequences")
    print(f"  overall          {total_score / total_pieces:.4f} points per piece")
    print(
        f"  per 10-game run  median {statistics.median(rates):.3f}  "
        f"min {rates[0]:.3f}  max {rates[-1]:.3f}"
    )
    print(
        f"  95th percentile  {rates[int(0.95 * len(rates)) - 1]:.3f}  "
        f"(RANDOM_CEILING is {RANDOM_CEILING})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", default=list(DEFAULT_RUNS))
    parser.add_argument("--ceiling", type=float, default=RANDOM_CEILING)
    parser.add_argument(
        "--measure-floor",
        action="store_true",
        help="re-measure the random ceiling instead (plays 200 games)",
    )
    args = parser.parse_args()

    if args.measure_floor:
        measure_floor()
        return

    print(f"dead = at or below {args.ceiling} points per piece on held-out seeds")
    print("(the 95th percentile of random play's own 10-game rate)\n")

    pooled: list[list[float]] = []
    first_last: list[tuple[bool, bool]] = []
    for run in args.runs:
        series = series_for(run)
        width = len(next(iter(series.values())))
        counts = [
            sum(1 for rates in series.values() if is_dead(rates[i], args.ceiling))
            for i in range(width)
        ]
        print(
            f"{run}: dead by iteration  "
            + "  ".join(f"it{i} {c}/{len(series)}" for i, c in enumerate(counts))
        )
        for (model, chain), rates in sorted(series.items()):
            marks = " ".join("D" if is_dead(r, args.ceiling) else "." for r in rates)
            print(f"    {model:<12} chain {chain}: {marks}")
        pooled.extend(series.values())
        first_last.extend(
            (is_dead(r[0], args.ceiling), is_dead(r[-1], args.ceiling)) for r in series.values()
        )
        print()

    start = sum(1 for before, _ in first_last if before)
    end = sum(1 for _, after in first_last if after)
    revived = sum(1 for before, after in first_last if before and not after)
    died = sum(1 for before, after in first_last if after and not before)
    print(
        f"pooled first -> last: dead {start}/{len(first_last)} -> {end}/{len(first_last)}"
        f"   revived {revived}, died {died}"
    )

    transitions = count_transitions(pooled, args.ceiling)
    pairs = sum(len(c) - 1 for c in pooled)
    print(
        f"pooled adjacent ({pairs} transitions): "
        f"{transitions.revivals} revivals, {transitions.deaths} deaths"
    )
    print(
        f"  sign test on the {transitions.discordant} discordant pairs: "
        f"p = {transitions.p_value:.3f}"
    )

    # Power is spent on discordant *pairs*, so the rate that matters is per
    # pair, not per chain: a chain contributes as many pairs as it has
    # iteration-to-iteration steps.
    per_pair = transitions.discordant / pairs if pairs else 0.0
    steps = len(pooled[0]) - 1 if pooled else 0
    print(
        f"\n{transitions.discordant} of {pairs} pairs changed state "
        f"({per_pair:.0%}); a {steps + 1}-iteration chain gives {steps} pairs."
    )
    print("chains for 80% power at that rate:")
    for share in (0.70, 0.80, 0.90):
        n = chains_needed(per_pair, share, pairs_per_chain=steps)
        label = f"{n} chains" if n else "more than 1000 chains"
        print(f"  revivals {share:.0%} of changed pairs -> {label}")


if __name__ == "__main__":
    main()
