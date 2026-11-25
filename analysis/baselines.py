"""Re-measure the reference players under every condition the docs quote.

The constants live in :mod:`tetris_bench.baselines` with their conditions; this
regenerates them, and exists because the project once published two different
heuristic rates with neither labelled.

    uv run python analysis/baselines.py          # ~20s
    uv run python analysis/baselines.py --exhaustion   # adds the 50,000-piece row, slow
"""

from __future__ import annotations

import argparse

from tetris_bench.baselines import (
    EVAL_SEEDS,
    HEURISTIC_RATE,
    MAX_PIECES,
    RANDOM_RATE,
    measure_heuristic,
    measure_random,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exhaustion",
        action="store_true",
        help="also run the heuristic to exhaustion at 50,000 pieces (minutes, not seconds)",
    )
    args = parser.parse_args()

    wide = tuple(range(1000, 1020))
    rows = [
        ("heuristic", EVAL_SEEDS, MAX_PIECES, "canonical: every model figure uses this"),
        ("heuristic", wide, MAX_PIECES, "the 20-seed table older write-ups quote"),
    ]
    if args.exhaustion:
        rows.append(("heuristic", wide, 50_000, "run to exhaustion"))

    print(f"{'player':<10} {'seeds':<12} {'budget':>7} {'pts/piece':>10} {'censored':>9}  note")
    for name, seeds, budget, note in rows:
        rate, _, _, censored = measure_heuristic(seeds, budget)
        label = f"{seeds[0]}-{seeds[-1]}"
        print(
            f"{name:<10} {label:<12} {budget:>7,} {rate:>10.2f} "
            f"{censored:>6}/{len(seeds):<2}  {note}"
        )

    rate, score, pieces = measure_random()
    print(
        f"{'random':<10} {f'{EVAL_SEEDS[0]}-{EVAL_SEEDS[-1]}':<12} {MAX_PIECES:>7,} "
        f"{rate:>10.2f} {'':>9}  pooled over 20 agent seeds "
        f"({score:,} pts / {pieces:,} pieces)"
    )

    print(
        f"\nPublished constants: HEURISTIC_RATE {HEURISTIC_RATE}, RANDOM_RATE {RANDOM_RATE}."
        "\nIf the canonical row above disagrees, update tetris_bench/baselines.py"
        " and every figure quoting it."
    )


if __name__ == "__main__":
    main()
