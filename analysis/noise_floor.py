"""Measure how much a model's score varies across repeated identical requests.

This is the threshold the improvement curve depends on. Generation is not
reproducible even at temperature 0 with a fixed seed -- the cause is numerics,
not sampling (see docs/findings/prompt-comparison-and-determinism.md) -- so
"iteration 4 beat iteration 3" means nothing until we know how much two runs of
the *same* iteration differ.

Everything is held fixed: one model, one prompt, one seed, one piece sequence,
one piece budget. The only thing that varies is the generation itself. What comes
out is the spread of scores attributable purely to nondeterminism.

Note the quantity that matters is **score** variance, not text variance. Two
different functions can play identically, and on qwen3-4b they did: four
generations, at least two distinct sources, every one scoring exactly 0. A rung
that produces varying scores is needed for this to be informative.

Results print as each run completes, so a partial run is still usable.

    uv run python analysis/noise_floor.py --model qwen3-14b --runs 5
"""

from __future__ import annotations

import argparse
import hashlib
import statistics
import time
from pathlib import Path

from tetris_bench.agents.strategy import StrategyAgent, request_scoring_function
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.config import ModelConfig, load_model_config
from tetris_bench.engine.game import Game
from tetris_bench.runner import play_game
from tetris_bench.sandbox import SandboxLimits, SandboxValidationError, ScoringSandbox


def one_run(
    index: int,
    config: ModelConfig,
    template: str,
    seed: int,
    max_pieces: int,
    save_dir: Path,
) -> dict:
    """Generate a function and play one game with it."""
    client = ModelClient(config)
    started = time.monotonic()
    generated = request_scoring_function(client, template=template)
    generation = time.monotonic() - started
    digest = hashlib.sha256(generated.source.encode()).hexdigest()[:12]
    generated.save(save_dir, f"{config.name}-noise{index}")

    row: dict = {
        "run": index,
        "digest": digest,
        "generation_seconds": generation,
        "tokens_out": client.usage.tokens_out,
        "score": None,
        "pieces": None,
        "rejected": False,
    }

    try:
        with ScoringSandbox(generated.source, limits=SandboxLimits()) as sandbox:
            agent = StrategyAgent(sandbox)
            result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
            row.update(
                score=result.score,
                pieces=result.pieces_placed,
                holes=result.final_holes,
                lines=result.lines_cleared,
                flat_moves=agent.diagnostics.flat_moves,
                moves=agent.diagnostics.moves,
                degenerate=agent.diagnostics.is_degenerate,
                sandbox_failures=sandbox.failures,
            )
    except SandboxValidationError as error:
        row.update(rejected=True, reason=str(error)[:120])

    if row["rejected"]:
        print(
            f"run {index}: {digest}  {generation:.0f}s  REJECTED: {row['reason']}",
            flush=True,
        )
    else:
        flag = " DEGENERATE" if row["degenerate"] else ""
        print(
            f"run {index}: {digest}  {generation:.0f}s  "
            f"score={row['score']:<6} pieces={row['pieces']:<4} "
            f"holes={row['holes']:<4} flat={row['flat_moves']}/{row['moves']}{flag}",
            flush=True,
        )
    return row


def report(rows: list[dict]) -> None:
    """Summarise the spread."""
    print(f"\n{'=' * 72}\nnoise floor\n{'=' * 72}")

    digests = {row["digest"] for row in rows}
    print(f"runs                 {len(rows)}")
    print(f"distinct functions   {len(digests)} of {len(rows)}")

    rejected = [row for row in rows if row["rejected"]]
    print(f"rejected by sandbox  {len(rejected)}")

    scored = [row for row in rows if not row["rejected"]]
    if not scored:
        print("no runs produced a score")
        return

    scores = [row["score"] for row in scored]
    print(f"scores               {sorted(scores)}")
    print(f"  min / max          {min(scores)} / {max(scores)}")
    print(f"  median             {statistics.median(scores)}")
    if len(scores) > 1:
        spread = max(scores) - min(scores)
        stdev = statistics.stdev(scores)
        print(f"  spread             {spread}")
        print(f"  stdev              {stdev:.1f}")
        mean = statistics.mean(scores)
        if mean:
            print(f"  coefficient of var {stdev / mean:.1%}")
        print()
        print("INTERPRETATION")
        # Three distinct cases, which a score spread alone cannot tell apart.
        if len(digests) == 1:
            print("  Every run produced the SAME function, byte for byte. Generation")
            print("  is reproducible on this rung, so there is no noise floor to")
            print("  clear: an iteration-to-iteration difference is real by")
            print("  construction. Verify this per rung rather than assuming it")
            print("  transfers -- it does not hold on every model.")
        elif spread == 0:
            print(f"  {len(digests)} distinct functions, all scoring the same. Text varies but")
            print("  the outcome does not, which happens when every function is")
            print("  degenerate or otherwise plays identically. Uninformative about")
            print("  the noise floor: try a rung whose scores actually move.")
        else:
            print(f"  An improvement between iterations must exceed ~{spread} points")
            print("  to be distinguishable from nondeterminism on this rung.")
            print(f"  Reporting a gain smaller than {spread} would be reporting noise.")

    degenerate = [row for row in scored if row["degenerate"]]
    print()
    print(f"degenerate functions {len(degenerate)} of {len(scored)}")
    print(f"generation seconds   {[round(r['generation_seconds']) for r in rows]}")
    print(f"output tokens        {[r['tokens_out'] for r in rows]}")
    print()
    print("reference, same game seed: heuristic 21600 / naive 2100 / random 0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-14b")
    parser.add_argument("--config", type=Path, default=Path("configs/models.yaml"))
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=1, help="piece sequence seed")
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument("--template", default="strategy_v2")
    parser.add_argument("--save-dir", type=Path, default=Path("runs/functions/noise"))
    args = parser.parse_args()

    config = load_model_config(args.config, args.model)
    print(
        f"model {config.name} ({config.model}) · temperature {config.temperature} · "
        f"model seed {config.seed}"
    )
    print(
        f"{args.runs} identical requests · template {args.template} · "
        f"game seed {args.seed} · {args.max_pieces} pieces\n"
    )

    rows = [
        one_run(index, config, args.template, args.seed, args.max_pieces, args.save_dir)
        for index in range(1, args.runs + 1)
    ]
    report(rows)


if __name__ == "__main__":
    main()
