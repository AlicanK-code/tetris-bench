"""Every published function, every model, on one axis against the baselines.

The power figure answers "did any model improve?". This answers the question a
reader asks first: **how good are these functions at all, and compared to
what?**

Every point is one of the 229 published scoring functions, replayed under the
*same* conditions — the ten held-out sequences at the 2,000-piece budget — so a
dot can be compared with a dot, with the reference players, and across models.
That matters more than it sounds: the published logs are not all comparable on
their own, because `clean-6iter` was played at the old 500-piece budget. Reading
rates straight out of the logs would put that run's numbers on a different
footing from everything else, which is the same class of mistake as quoting a
baseline without its conditions.

The shape of the distribution is the result. Most functions sit near zero, a
handful reach the hand-written heuristic, and the gap between the best and the
median of the same model's attempts is far larger than any gain the improvement
loop produced.

    uv run python analysis/comparison_figure.py            # uses the cached replay
    uv run python analysis/comparison_figure.py --replay   # re-runs it, ~10 min
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

import matplotlib

# Must precede the pyplot import; a sweep box has no display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from tetris_bench.baselines import (  # noqa: E402
    EVAL_SEEDS,
    HEURISTIC,
    MAX_PIECES,
    RANDOM,
)

PUBLISHED = Path("runs/published")
CACHE = PUBLISHED / "replayed-at-canonical.json"
MODELS = ("qwen3-4b", "qwen3-8b", "qwen3-14b", "qwen3-30b")
COLOUR = "#1f77b4"


def replay_all() -> list[dict]:
    """Replay every published function under the canonical conditions."""
    from tetris_bench.agents.strategy import StrategyAgent
    from tetris_bench.engine.game import Game
    from tetris_bench.runner import play_game
    from tetris_bench.sandbox import SandboxError, SandboxLimits, ScoringSandbox

    rows: list[dict] = []
    files = sorted(PUBLISHED.glob("*/functions/*.py"))
    for n, path in enumerate(files, 1):
        match = re.match(r"(qwen3-[0-9]+b)-chain(\d+)-iter(\d+)", path.stem)
        if not match:
            continue
        # ("runs", "published", "<run>", "functions", "<file>")
        row = {"model": match.group(1), "run": path.parts[2], "stem": path.stem}
        try:
            score = pieces = 0
            with ScoringSandbox(path.read_text(), limits=SandboxLimits()) as box:
                agent = StrategyAgent(box)
                for seed in EVAL_SEEDS:
                    result = play_game(Game(seed=seed, max_pieces=MAX_PIECES), agent)
                    score += result.score
                    pieces += result.pieces_placed
            row |= {"rate": score / pieces if pieces else 0.0, "score": score, "pieces": pieces}
        except SandboxError as error:
            # A rejected function is a real outcome, not a gap: it is excluded
            # from the plot and counted in the caption instead.
            row |= {"rate": None, "error": str(error)[:120]}
        rows.append(row)
        if n % 40 == 0:
            print(f"  {n}/{len(files)}", flush=True)
    return rows


def draw(rows: list[dict], out: Path) -> Path:
    figure, axis = plt.subplots(figsize=(11, 5.6))

    for y, model in enumerate(MODELS):
        rates = sorted(r["rate"] for r in rows if r["model"] == model and r["rate"] is not None)
        if not rates:
            continue
        jitter = [y + 0.16 * ((i % 7) - 3) / 3 for i in range(len(rates))]
        axis.scatter(rates, jitter, s=26, alpha=0.35, color=COLOUR, edgecolors="none", zorder=3)

        median, best = statistics.median(rates), max(rates)
        axis.plot([median], [y], "|", color="#0b3d63", markersize=26, markeredgewidth=3, zorder=5)
        axis.plot([best], [y], "o", color="#d62728", markersize=9, zorder=6)
        axis.annotate(
            f"best {best:.1f}",
            (best, y),
            textcoords="offset points",
            xytext=(10, 7),
            fontsize=9,
            color="#d62728",
            fontweight="bold",
        )
        # Placed well right of the cluster of dead functions at x ~ 0, which it
        # used to sit on top of.
        axis.annotate(
            f"median {median:.1f} of {len(rates)} functions",
            (median, y - 0.33),
            ha="center",
            fontsize=8,
            color="#0b3d63",
        )

    for baseline, style, colour in ((RANDOM, ":", "#888888"), (HEURISTIC, "--", "#2ca02c")):
        axis.axvline(baseline.rate, linestyle=style, color=colour, linewidth=1.8, zorder=2)
        axis.annotate(
            f"{baseline.name} {baseline.rate:g}",
            (baseline.rate, -0.72),
            textcoords="offset points",
            xytext=(6, 0),
            rotation=90,
            va="bottom",
            fontsize=9,
            color=colour,
            fontweight="bold",
        )

    axis.set_yticks(range(len(MODELS)))
    axis.set_yticklabels(MODELS)
    axis.set_ylim(-0.75, len(MODELS) - 0.4)
    axis.set_xlabel(
        "points per piece — every published function, replayed on the same ten\n"
        "held-out sequences at the 2,000-piece budget"
    )
    axis.set_title(
        "Most model-written scorers are far worse than a hand-written heuristic,\n"
        "and the spread within one model dwarfs anything the improvement loop moved",
        fontsize=12,
    )
    axis.grid(axis="x", alpha=0.25)
    axis.set_axisbelow(True)

    out.mkdir(parents=True, exist_ok=True)
    path = out / "functions-vs-baselines.png"
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay", action="store_true", help="re-run the replay instead of using the cache"
    )
    parser.add_argument("--out", type=Path, default=PUBLISHED / "figures")
    args = parser.parse_args()

    if args.replay or not CACHE.exists():
        rows = replay_all()
        CACHE.write_text(json.dumps(rows, indent=1) + "\n")
        print(f"cached {len(rows)} replays in {CACHE}")
    else:
        rows = json.loads(CACHE.read_text())

    playable = [r for r in rows if r["rate"] is not None]
    rejected = len(rows) - len(playable)
    print(f"{len(playable)} functions replayed, {rejected} refused by the validator")
    for model in MODELS:
        rates = [r["rate"] for r in playable if r["model"] == model]
        if rates:
            dead = sum(1 for x in rates if x <= RANDOM.rate)
            print(
                f"  {model:<10} n={len(rates):<3} median {statistics.median(rates):6.2f}  "
                f"best {max(rates):6.2f}  at or below random: {dead}"
            )
    print(f"\nwrote {draw(playable, args.out)}")


if __name__ == "__main__":
    main()
