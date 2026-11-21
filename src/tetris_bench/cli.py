"""Command-line entry points.

Currently one subcommand, ``play``, which runs a single game with a baseline
agent. Declared in ``pyproject.toml`` as the ``tetris-bench`` script, so::

    uv run tetris-bench play --agent heuristic --seed 1
    uv run tetris-bench play --agent random --show-state --log runs/baseline.jsonl
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from tetris_bench.agents.base import Agent
from tetris_bench.agents.heuristic import heuristic_agent
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.clients.config import ModelConfig, load_model_configs
from tetris_bench.engine.game import DEFAULT_MAX_PIECES, Game
from tetris_bench.jsonl import append_record
from tetris_bench.records import GameResult
from tetris_bench.render import render_board, render_state
from tetris_bench.runner import play_game

AGENT_NAMES = ("random", "heuristic")


def positive_int(value: str) -> int:
    """An argparse type for counts that must be at least 1.

    ``Game`` already refuses a budget below 1, but raising there would surface a
    traceback to someone who simply mistyped a flag. Validating here turns it
    into argparse's usual usage message, at the point of the actual mistake.
    """
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {number}")
    return number


def build_agent(name: str, agent_seed: int) -> Agent:
    """Construct a baseline agent by name.

    Only the random agent needs a seed of its own; the heuristic is
    deterministic, so its ``agent_seed`` is irrelevant and reported as ``None``.
    """
    if name == "random":
        return RandomAgent(seed=agent_seed)
    if name == "heuristic":
        return heuristic_agent()
    raise ValueError(f"unknown agent {name!r}, expected one of {AGENT_NAMES}")


def format_result(result: GameResult, board: str) -> str:
    """Render a finished game for the terminal."""
    return "\n".join(
        [
            board,
            "",
            f"agent          {result.agent}",
            f"piece seed     {result.seed}",
            f"agent seed     {result.agent_seed if result.agent_seed is not None else '-'}",
            f"score          {result.score}",
            f"lines cleared  {result.lines_cleared}",
            f"pieces placed  {result.pieces_placed}",
            f"ended by       {result.cause}",
            f"max height     {result.final_max_height} (avg {result.avg_max_height:.1f})",
            f"holes          {result.final_holes} (avg {result.avg_holes:.1f})",
            f"bumpiness      {result.final_bumpiness} (avg {result.avg_bumpiness:.1f})",
        ]
    )


EPILOG = """\
examples:
  tetris-bench play --agent heuristic --seed 1
  tetris-bench play --agent random --agent-seed 0 --seed 1 --quiet
  tetris-bench play --seed 1 --max-pieces 60 --show-state
  tetris-bench play --agent heuristic --seed 1 --log runs/baseline.jsonl
  tetris-bench models --config configs/models.yaml
  tetris-bench strategy --model qwen3-4b --seed 1
  tetris-bench loop --model qwen3-14b --iterations 6
  tetris-bench loop --model qwen3-30b --chains 5
"""


DEFAULT_MODEL_CONFIG = Path("configs/models.yaml")


def format_models(configs: list[ModelConfig], environ: dict[str, str]) -> str:
    """Render the configured models as a table.

    Reports whether each cloud model's key is present in the environment, which
    is the one setup mistake worth catching before a run rather than during it.
    No network is touched: this validates configuration, not connectivity.
    """
    rows = [("name", "provider", "model", "in $/M", "out $/M", "key")]
    for config in configs:
        spec = config.provider_spec
        if not spec.requires_key:
            key = "not needed"
        elif environ.get(spec.api_key_env or ""):
            key = f"{spec.api_key_env} set"
        else:
            key = f"{spec.api_key_env} MISSING"
        rows.append(
            (
                config.name,
                config.provider,
                config.model,
                f"{config.pricing.input_per_million:g}",
                f"{config.pricing.output_per_million:g}",
                key,
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in rows
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Separate from :func:`main` so tests can use it.

    The description is written out rather than taken from ``__doc__``: argparse
    reflows whatever it is given, which turns a multi-line module docstring into
    one unreadable run-on. ``RawDescriptionHelpFormatter`` preserves the example
    block's line breaks.
    """
    parser = argparse.ArgumentParser(
        prog="tetris-bench",
        description="Benchmark how well LLMs improve at Tetris across repeated attempts.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    play = sub.add_parser("play", help="play one game with a baseline agent")
    play.add_argument("--agent", choices=AGENT_NAMES, default="heuristic")
    play.add_argument("--seed", type=int, default=1, help="piece sequence seed")
    play.add_argument("--agent-seed", type=int, default=0, help="random agent's own seed")
    play.add_argument("--max-pieces", type=positive_int, default=DEFAULT_MAX_PIECES)
    play.add_argument("--quiet", action="store_true", help="print one summary line only")
    play.add_argument(
        "--show-state",
        action="store_true",
        help="print the model-facing state instead of the result summary",
    )
    play.add_argument("--show-pieces", action="store_true", help="render piece letters, not '#'")
    play.add_argument("--log", type=Path, default=None, help="append the result to a JSONL file")

    models = sub.add_parser("models", help="list and validate configured models")
    models.add_argument("--config", type=Path, default=DEFAULT_MODEL_CONFIG)

    strategy = sub.add_parser(
        "strategy", help="ask a model for a scoring function, then play with it"
    )
    strategy.add_argument("--model", required=True, help="a name from the model config")
    strategy.add_argument("--config", type=Path, default=DEFAULT_MODEL_CONFIG)
    strategy.add_argument("--seed", type=int, default=1, help="piece sequence seed")
    strategy.add_argument("--max-pieces", type=positive_int, default=DEFAULT_MAX_PIECES)
    strategy.add_argument(
        "--per-call-seconds", type=float, default=1.0, help="time budget per placement"
    )
    strategy.add_argument(
        "--save-dir",
        type=Path,
        default=Path("runs/functions"),
        help="where to log the generated function",
    )
    strategy.add_argument("--log", type=Path, default=None, help="append the result to JSONL")
    strategy.add_argument("--show-source", action="store_true", help="print the function")
    strategy.add_argument(
        "--template", default=None, help="prompt template name (default: the current version)"
    )

    loop = sub.add_parser("loop", help="run the improvement loop: feedback, revise, replay, repeat")
    loop.add_argument("--model", required=True, help="a name from the model config")
    loop.add_argument("--config", type=Path, default=DEFAULT_MODEL_CONFIG)
    loop.add_argument(
        "--train-seeds",
        type=int,
        nargs="+",
        default=[1, 2, 17],
        help="sequences whose outcomes are fed back to the model",
    )
    loop.add_argument(
        "--eval-seeds",
        type=int,
        nargs="+",
        default=list(range(1000, 1010)),
        help="held-out sequences; the curve is read from these",
    )
    loop.add_argument("--iterations", type=positive_int, default=6)
    loop.add_argument(
        "--chains",
        type=positive_int,
        default=1,
        help="independent chains per seed; use 1 for a reproducible rung, more otherwise",
    )
    loop.add_argument("--max-pieces", type=positive_int, default=DEFAULT_MAX_PIECES)
    loop.add_argument("--per-call-seconds", type=float, default=1.0)
    loop.add_argument("--log", type=Path, default=Path("runs/loop.jsonl"))
    loop.add_argument("--save-dir", type=Path, default=Path("runs/functions"))
    return parser


def main() -> None:
    """Entry point for the ``tetris-bench`` script."""
    args = build_parser().parse_args()

    if args.command == "play":
        game = Game(seed=args.seed, max_pieces=args.max_pieces)
        agent = build_agent(args.agent, args.agent_seed)
        result = play_game(game, agent, agent_seed=getattr(agent, "seed", None))

        if args.log is not None:
            append_record(args.log, result)

        if args.show_state:
            print(render_state(game, show_pieces=args.show_pieces))
        elif args.quiet:
            print(
                f"{result.agent} seed={result.seed} score={result.score} "
                f"lines={result.lines_cleared} pieces={result.pieces_placed} "
                f"cause={result.cause}"
            )
        else:
            board = render_board(game.board, show_pieces=args.show_pieces)
            print(format_result(result, board))

    elif args.command == "models":
        print(format_models(load_model_configs(args.config), dict(os.environ)))

    elif args.command == "strategy":
        run_strategy(args)

    elif args.command == "loop":
        run_improvement_loop(args)


def run_improvement_loop(args: argparse.Namespace) -> None:
    """Run the improvement loop. Imported lazily, like `strategy`."""
    from tetris_bench.clients.client import ModelClient
    from tetris_bench.clients.config import load_model_config
    from tetris_bench.loop import LoopConfig, run_loop

    config = load_model_config(args.config, args.model)
    client = ModelClient(config)
    loop_config = LoopConfig(
        model=config.name,
        train_seeds=tuple(args.train_seeds),
        eval_seeds=tuple(args.eval_seeds),
        iterations=args.iterations,
        chains=args.chains,
        max_pieces=args.max_pieces,
        per_call_seconds=args.per_call_seconds,
        # Chain k generates under `seed + k`, so chains are independent samples
        # rather than identical copies. Chain 0 keeps the configured seed.
        model_seed=config.seed,
        log_path=args.log,
        functions_dir=args.save_dir,
    )
    total = loop_config.chains * loop_config.iterations
    print(
        f"{config.name} ({config.model}): {total} generations "
        f"({loop_config.chains} chain(s) x {loop_config.iterations} iterations)"
    )
    print(
        f"train seeds {list(loop_config.train_seeds)} fed back; "
        f"{len(loop_config.eval_seeds)} held-out seeds evaluated per iteration"
    )
    print(f"log {loop_config.log_path} - rerun the same command to resume\n")
    run_loop(client, loop_config)


def run_strategy(args: argparse.Namespace) -> None:
    """Ask a model for a scoring function, then play a game with it.

    Imported here rather than at module scope so that `play` and `models` keep
    working when the optional `llm` extra is not installed.
    """
    from tetris_bench.agents.strategy import StrategyAgent, request_scoring_function
    from tetris_bench.clients.client import ModelClient
    from tetris_bench.clients.config import load_model_config
    from tetris_bench.jsonl import append_record
    from tetris_bench.records import ModelUsage, RunRecord
    from tetris_bench.sandbox import SandboxLimits, SandboxValidationError, ScoringSandbox

    config = load_model_config(args.config, args.model)
    client = ModelClient(config)

    print(f"asking {config.name} ({config.model}) for a scoring function...")
    generated = request_scoring_function(client, per_call_seconds=args.per_call_seconds)
    stem = f"{config.name}-seed{args.seed}-iter{generated.iteration}"
    saved = generated.save(args.save_dir, stem)
    print(f"saved {saved}")

    if args.show_source:
        print()
        print(generated.source)

    limits = SandboxLimits(per_call_seconds=args.per_call_seconds)
    try:
        with ScoringSandbox(generated.source, limits=limits) as sandbox:
            agent = StrategyAgent(sandbox)
            game = Game(seed=args.seed, max_pieces=args.max_pieces)
            result = play_game(game, agent)
            failures = sandbox.failures
            sample = list(sandbox.errors)
            diagnostics = agent.diagnostics
    except SandboxValidationError as error:
        print(f"\nREJECTED: {error}")
        print("the model's function was not run; it is saved above for inspection")
        return

    print()
    print(render_board(game.board))
    print()
    print(f"score          {result.score}")
    print(f"lines cleared  {result.lines_cleared}")
    print(f"pieces placed  {result.pieces_placed}")
    print(f"ended by       {result.cause}")
    print(f"holes          {result.final_holes} (avg {result.avg_holes:.1f})")
    print(f"max height     {result.final_max_height} (avg {result.avg_max_height:.1f})")
    print(f"sandbox fails  {failures}")
    print(f"score spread   {diagnostics.summary()}")
    for line in sample[:3]:
        print(f"  {line}")
    if diagnostics.is_degenerate:
        print()
        print(
            "NOTE: the function scored every candidate the same, so the engine had\n"
            "      nothing to choose on and played the first legal move each time.\n"
            "      A zero score here reflects a dead function, not a bad strategy."
        )
    usage = client.usage
    print(
        f"model          {usage.model_calls} call(s), {usage.tokens_in} in / "
        f"{usage.tokens_out} out, {usage.latency_seconds:.1f}s"
    )

    if args.log is not None:
        append_record(
            args.log,
            RunRecord(
                game=result,
                model=config.name,
                mode="strategy",
                iteration=generated.iteration,
                usage=ModelUsage(
                    model_calls=usage.model_calls,
                    tokens_in=usage.tokens_in,
                    tokens_out=usage.tokens_out,
                    latency_seconds=usage.latency_seconds,
                    estimated_cost_usd=usage.estimated_cost_usd,
                    sandbox_failures=failures,
                    retries=usage.retries,
                    failed_calls=usage.failed_calls,
                ),
            ),
        )
