"""Replay saved scoring functions on seeds they were never shown.

Every score this project has reported so far comes from the single piece sequence
the function was written against. That makes two things unmeasurable.

**Generalization.** The improvement loop shows a model outcomes from one seed and
lets it revise against them for N iterations. That is selection against one piece
sequence through the feedback channel, which is overfitting even with no gradient
involved. Nothing has been held out, so nothing distinguishes "this function got
better at Tetris" from "this function got better at seed 1".

**Seed noise.** A fixed, deterministic policy already varies enormously across
seeds: the naive baseline scores 2,100 / 500 / 2,800 / 1,300 on seeds
1 / 2 / 17 / 123 -- a coefficient of variation near 60%. A single-seed score is
therefore a noisy estimate of a function's quality, on top of the generation
noise already measured in docs/findings/.

Both are fixable for free. A saved function replays in well under a second, so
evaluating on twenty unseen seeds costs no generation time at all and cuts seed
noise by about root-20.

    uv run python analysis/held_out.py
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from tetris_bench.agents.heuristic import heuristic_agent
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.agents.strategy import StrategyAgent
from tetris_bench.engine.game import Game
from tetris_bench.runner import play_game
from tetris_bench.sandbox import SandboxLimits, SandboxValidationError, ScoringSandbox

#: Seeds used for training/reporting so far, and so excluded from the held-out set.
TRAINING_SEEDS = (1, 2, 17, 123)
HELD_OUT_SEEDS = tuple(range(1000, 1020))


def replay(source: str, seeds: tuple[int, ...], max_pieces: int) -> list[tuple[int, int]]:
    """Play one function on many seeds, reusing a single sandbox worker."""
    results: list[tuple[int, int]] = []
    with ScoringSandbox(source, limits=SandboxLimits()) as sandbox:
        agent = StrategyAgent(sandbox)
        for seed in seeds:
            result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
            results.append((result.score, result.pieces_placed))
    return results


def baseline(kind: str, seeds: tuple[int, ...], max_pieces: int) -> list[tuple[int, int]]:
    """Play a reference agent on many seeds, for comparison."""
    out: list[tuple[int, int]] = []
    for seed in seeds:
        agent = heuristic_agent() if kind == "heuristic" else RandomAgent(seed=0)
        result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
        out.append((result.score, result.pieces_placed))
    return out


def summarise(label: str, train: list[tuple[int, int]], held: list[tuple[int, int]]) -> dict:
    """Collapse a replay into the numbers that matter."""
    train_scores = [s for s, _ in train]
    held_scores = [s for s, _ in held]
    held_pieces = [p for _, p in held]
    mean = statistics.mean(held_scores)
    stdev = statistics.stdev(held_scores) if len(held_scores) > 1 else 0.0
    return {
        "label": label,
        "train_score": train_scores[0] if train_scores else 0,
        "held_mean": mean,
        "held_stdev": stdev,
        "held_cv": (stdev / mean) if mean else float("nan"),
        "held_min": min(held_scores),
        "held_max": max(held_scores),
        "pieces_mean": statistics.mean(held_pieces),
        "pieces_stdev": statistics.stdev(held_pieces) if len(held_pieces) > 1 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functions-dir", type=Path, default=Path("runs/functions"))
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument("--train-seed", type=int, default=1)
    args = parser.parse_args()

    sources = sorted(args.functions_dir.rglob("*.py"))
    print(
        f"{len(sources)} saved function(s); held-out seeds {HELD_OUT_SEEDS[0]}-{HELD_OUT_SEEDS[-1]}"
    )
    print(f"training seeds so far: {TRAINING_SEEDS}\n")

    rows: list[dict] = []

    for kind in ("heuristic", "random"):
        train = baseline(kind, (args.train_seed,), args.max_pieces)
        held = baseline(kind, HELD_OUT_SEEDS, args.max_pieces)
        rows.append(summarise(f"[baseline] {kind}", train, held))

    for path in sources:
        source = path.read_text()
        try:
            train = replay(source, (args.train_seed,), args.max_pieces)
            held = replay(source, HELD_OUT_SEEDS, args.max_pieces)
        except SandboxValidationError as error:
            print(f"skip {path.name}: {str(error)[:60]}")
            continue
        rows.append(summarise(path.stem, train, held))

    header = (
        f"{'function':34} {'seed1':>7} {'held mean':>10} {'held sd':>8} "
        f"{'cv':>6} {'min':>6} {'max':>7} {'pieces':>7}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['label'][:34]:34} {row['train_score']:>7} {row['held_mean']:>10.0f} "
            f"{row['held_stdev']:>8.0f} {row['held_cv']:>6.0%} {row['held_min']:>6} "
            f"{row['held_max']:>7} {row['pieces_mean']:>7.0f}"
        )

    print()
    print("SEED NOISE: a fixed function's spread across seeds it never saw.")
    print("Any single-seed score carries this much uncertainty about its quality.")

    models = [r for r in rows if not r["label"].startswith("[baseline]")]
    if len(models) > 1:
        scores = [r["held_mean"] for r in models]
        pieces = [r["pieces_mean"] for r in models]
        print()
        print("SEPARATION: which variable distinguishes these functions better?")
        print(
            f"  held-out score  range {min(scores):.0f}-{max(scores):.0f}, "
            f"{sum(1 for s in scores if s == 0)} of {len(scores)} at exactly 0"
        )
        print(
            f"  pieces placed   range {min(pieces):.0f}-{max(pieces):.0f}, "
            f"{sum(1 for p in pieces if p == 0)} of {len(pieces)} at exactly 0"
        )
        print("  A variable with many ties at zero cannot show a curve rising off the floor.")


if __name__ == "__main__":
    main()
