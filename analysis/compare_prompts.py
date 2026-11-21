"""Compare prompt templates on one model and seed, holding everything else fixed.

Temperature is 0, so the only variable between runs is the prompt text. That
makes this a clean read on what wording alone is worth -- which matters for a
benchmark about iteration, since a gain that came from the harness rather than
from the model's own revision would be a confound.

One sample per template: deterministic, but it does not capture how much a
model's output varies across rewordings in general. Treat a difference as a
signal to investigate, not a measured effect size.

    uv run python analysis/compare_prompts.py --model qwen3-4b --seed 1
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tetris_bench.agents.strategy import (
    StrategyAgent,
    request_scoring_function,
)
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.config import load_model_config
from tetris_bench.engine.game import Game
from tetris_bench.runner import play_game
from tetris_bench.sandbox import SandboxLimits, SandboxValidationError, ScoringSandbox


def run_one(client: ModelClient, template: str, seed: int, max_pieces: int, save_dir: Path) -> dict:
    """Ask for a function with one template, then play a game with it."""
    print(f"\n{'=' * 70}\n{template}\n{'=' * 70}", flush=True)

    client.reset_usage()
    started = time.monotonic()
    generated = request_scoring_function(client, template=template)
    generation = time.monotonic() - started
    usage = client.usage

    generated.save(save_dir, f"{client.config.name}-seed{seed}-{template}")
    print(generated.source, flush=True)
    print(
        f"generation: {generation:.0f}s, {usage.tokens_in} in / {usage.tokens_out} out",
        flush=True,
    )

    row = {
        "template": template,
        "generation_seconds": generation,
        "tokens_in": usage.tokens_in,
        "tokens_out": usage.tokens_out,
        "reasoning_chars": len(generated.reasoning),
        "source_chars": len(generated.source),
    }

    try:
        with ScoringSandbox(generated.source, limits=SandboxLimits()) as sandbox:
            agent = StrategyAgent(sandbox)
            game = Game(seed=seed, max_pieces=max_pieces)
            result = play_game(game, agent)
            row.update(
                rejected=False,
                score=result.score,
                lines=result.lines_cleared,
                pieces=result.pieces_placed,
                cause=result.cause,
                holes=result.final_holes,
                sandbox_failures=sandbox.failures,
                moves=agent.diagnostics.moves,
                flat_moves=agent.diagnostics.flat_moves,
                mean_spread=agent.diagnostics.mean_spread,
                degenerate=agent.diagnostics.is_degenerate,
            )
            print(f"result: score={result.score} pieces={result.pieces_placed} ", flush=True)
            print(f"spread: {agent.diagnostics.summary()}", flush=True)
    except SandboxValidationError as error:
        row.update(rejected=True, reason=str(error)[:200], score=0, pieces=0)
        print(f"REJECTED: {error}", flush=True)

    return row


def reference_line(seed: int, max_pieces: int) -> str:
    """Play the reference agents on this exact game, rather than quote a literal.

    This used to be a hardcoded string, `heuristic 21600 / naive 2100 /
    random 0`, and both halves rotted: the piece budget changed from 500 to
    2000, which moved the heuristic's score by a factor of four, and no `naive`
    agent was ever implemented -- the number survived only in print statements
    like this one. A reference that is computed cannot drift away from the run
    it is printed beside, and these games cost a second or two of CPU with no
    model involved.
    """
    from tetris_bench.agents.heuristic import heuristic_agent
    from tetris_bench.agents.random_agent import RandomAgent

    scores = {}
    for name, agent in (("heuristic", heuristic_agent()), ("random", RandomAgent(seed=0))):
        outcome = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
        capped = " (censored)" if outcome.cause == "piece_limit" else ""
        scores[name] = f"{outcome.score:,}{capped}"
    return (
        f"reference on seed {seed} at {max_pieces} pieces: "
        f"heuristic {scores['heuristic']} / random {scores['random']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-4b")
    parser.add_argument("--config", type=Path, default=Path("configs/models.yaml"))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument("--templates", nargs="+", default=["strategy_v1", "strategy_v2"])
    parser.add_argument("--save-dir", type=Path, default=Path("runs/functions"))
    args = parser.parse_args()

    config = load_model_config(args.config, args.model)
    client = ModelClient(config)
    print(
        f"model {config.name} ({config.model}), seed {args.seed}, temperature {config.temperature}"
    )

    rows = [
        run_one(client, template, args.seed, args.max_pieces, args.save_dir)
        for template in args.templates
    ]

    print(f"\n{'=' * 70}\ncomparison\n{'=' * 70}")
    print(
        f"{'template':14} {'score':>7} {'pieces':>7} {'holes':>6} "
        f"{'flat':>9} {'spread':>9} {'gen s':>7} {'out tok':>8}"
    )
    for row in rows:
        if row.get("rejected"):
            print(f"{row['template']:14} {'REJECTED':>7}  {row.get('reason', '')[:40]}")
            continue
        flat = f"{row['flat_moves']}/{row['moves']}"
        print(
            f"{row['template']:14} {row['score']:>7} {row['pieces']:>7} {row['holes']:>6} "
            f"{flat:>9} {row['mean_spread']:>9.3g} {row['generation_seconds']:>7.0f} "
            f"{row['tokens_out']:>8}"
        )
    print()
    print(reference_line(args.seed, args.max_pieces))


if __name__ == "__main__":
    main()
