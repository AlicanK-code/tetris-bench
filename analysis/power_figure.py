"""The whole negative result in one picture: four gains against four noise bars.

The per-rung curves in ``analysis/plots.py`` each answer "did this rung
improve?". This answers the question the project is actually making a claim
about: **did any of them, and how far short did they fall?** Four rungs, four
gains, four bars each rung had to clear -- and none does.

The arithmetic is :mod:`tetris_bench.power`, which is unit-tested with these
figures pinned, so this file only draws.

Drawn as a bar each rung had to clear rather than as a p-value, because a null
here is a *bounded* null and the bound is the interesting part. A reader should
be able to see at a glance that the 30B's +7.37 is a different kind of
not-significant from the 8B's +2.51: the first is a respectable gain measured
too coarsely, the second is a small gain measured well.

    uv sync --all-extras
    uv run python analysis/power_figure.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

# Must precede the pyplot import; a sweep box has no display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from tetris_bench.curves import build_curves  # noqa: E402
from tetris_bench.power import RungPower, summarise  # noqa: E402

PUBLISHED = Path("runs/published")

#: Smallest rung first, so the x axis is the capability ladder.
RUNS = (
    ("4b-loop", "qwen3-4b\n5 chains"),
    ("8b-loop", "qwen3-8b\n10 chains"),
    ("five-chain", "qwen3-14b\n5 chains"),
    ("30b-pilot", "qwen3-30b\n6 chains"),
)

GAIN = "#1f77b4"
LOSS = "#d62728"
BAR = "#9e9e9e"


def load(run: str) -> RungPower:
    rows = [json.loads(line) for line in (PUBLISHED / run / "loop.jsonl").open()]
    spread = next(curve.chain_spread() for curve in build_curves(rows))
    return summarise(rows, spread)


def draw(rungs: list[tuple[RungPower, str]], out: Path) -> Path:
    figure, axis = plt.subplots(figsize=(10, 6))
    positions = range(len(rungs))

    for x, (power, _) in zip(positions, rungs, strict=True):
        # The bar is symmetric: a fall of more than the MDE would be detectable
        # too, and the 4B's gain is negative, so drawing only the upper half
        # would make that rung look unmeasured rather than measured and flat.
        axis.add_patch(
            plt.Rectangle(
                (x - 0.34, -power.mde),
                0.68,
                2 * power.mde,
                facecolor=BAR,
                alpha=0.22,
                edgecolor=BAR,
                linewidth=1.0,
                zorder=1,
            )
        )
        axis.plot(
            [x - 0.34, x + 0.34],
            [power.mde, power.mde],
            color=BAR,
            linewidth=1.4,
            zorder=2,
        )
        axis.annotate(
            f"detectable\n±{power.mde:.1f}",
            (x + 0.37, power.mde),
            fontsize=8,
            color="#555555",
            va="center",
        )

    for x, (power, _) in zip(positions, rungs, strict=True):
        colour = GAIN if power.median_gain >= 0 else LOSS
        axis.plot([x, x], [0, power.median_gain], color=colour, linewidth=2.5, zorder=3)
        axis.plot([x], [power.median_gain], "o", color=colour, markersize=11, zorder=4)
        offset = 1.6 if power.median_gain >= 0 else -1.6
        axis.annotate(
            f"{power.median_gain:+.2f}",
            (x, power.median_gain + offset),
            ha="center",
            fontsize=11,
            fontweight="bold",
            color=colour,
            zorder=5,
        )

    axis.axhline(0, color="#333333", linewidth=1.0, zorder=2)
    axis.set_xticks(list(positions))
    # Sigma belongs on the tick, not floating at the bottom of the band, where
    # on the 30B it lands on the band's own edge.
    axis.set_xticklabels(
        [f"{label}\nσ {power.paired_sd:.2f}" for power, label in rungs], fontsize=9
    )
    axis.set_ylabel("median gain, held-out points per piece\n(iteration 0 to last)")
    axis.set_title(
        "Every rung's gain is inside the gain it could have detected\n"
        "grey band: the smallest change 80% power would resolve, from that rung's "
        "own paired σ — no rung clears it",
        fontsize=12,
    )
    axis.set_xlim(-0.6, len(rungs) - 0.1)
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)

    out.mkdir(parents=True, exist_ok=True)
    path = out / "power-four-rungs.png"
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("analysis/figures"))
    args = parser.parse_args()

    rungs = [(load(run), label) for run, label in RUNS]
    for power, _ in rungs:
        needed = power.chains_for_observed()
        print(
            f"{power.model:<10} n={power.chains:<3} gain {power.median_gain:+6.2f}  "
            f"σ {power.paired_sd:5.2f}  detectable ±{power.mde:5.2f}  "
            f"detected={power.detected}  "
            f"chains for its own gain: {needed}"
        )
    print(f"\nwrote {draw(rungs, args.out)}")


if __name__ == "__main__":
    main()
