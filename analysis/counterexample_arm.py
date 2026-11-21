"""Does a feature-level counterexample fix what outcome feedback cannot?

Both of the 14B's outcome-feedback revisions kept its broken hole count
character-for-character and only changed the weights
(docs/findings/first-revision-reweights-not-debugs.md). Told "you finished with
96 holes", it concluded "penalise holes more" rather than "my hole count may be
wrong" -- which is a reasonable reading, because "96 holes" is equally consistent
with a correct count and a bad weight.

This arm tests whether the bottleneck is **credit assignment** rather than
capability. It gives the identical outcome feedback the control received, plus
one extra block: for one specific board, the values the engine measures. The
model then has labelled data at the level its bug lives at, and has to notice
that its own code disagrees.

What the block deliberately does not contain: any statement that the hole count
is wrong, which direction it scans, or what a hole is. It is a counterexample,
not a diagnosis -- otherwise the result would only show that a model can apply a
fix it was handed.

Control, already collected: runs/functions/revise/qwen3-14b-revise{1,2}.py,
held-out 130 and 85 against iteration 0's 110.

Three runs on the board at piece 16 gave two distinct functions, both of which
fixed the bug -- but all three used the *identical* prompt, so they measure
generation variance, not whether the effect survives a different board. If the
fix only appears for one board, what was measured is "this board localises this
bug" rather than "a feature-level trace localises bugs". `--trace-at` varies it.

    uv run python analysis/counterexample_arm.py --model qwen3-14b
    uv run python analysis/counterexample_arm.py --trace-at 8 --runs 1
"""

from __future__ import annotations

import argparse
import hashlib
import statistics
import time
from dataclasses import replace
from pathlib import Path

from tetris_bench.agents.strategy import StrategyAgent, extract_code
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.config import load_model_config
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.loop import (
    MEASUREMENT_DECLARATION,
    LoopConfig,
    Outcome,
    feedback_text,
    play_function,
)
from tetris_bench.metrics import holes
from tetris_bench.prompts import render
from tetris_bench.render import render_board
from tetris_bench.runner import play_game
from tetris_bench.sandbox import ScoringSandbox

HELD_OUT_SEEDS = tuple(range(1000, 1020))


def trace_block(boards: list[tuple[str, Board]]) -> str:
    """Per-board ground truth, at the level a feature bug lives at.

    Reports what the engine measures and nothing about what the function got
    wrong. The model has to trace its own code against this.
    """
    # The first version of this block showed two boards and instructed the model
    # to "work out what your own code computes for these same boards, and
    # compare". That induced over twenty minutes of generation -- it attempted to
    # hand-trace a nested loop across 400 cells -- and timed out. The data is the
    # counterexample; demanding an exhaustive trace is not part of it, and the
    # shorter block also keeps the prompt-length difference from the control
    # smaller.
    noun = "one specific board" if len(boards) == 1 else f"{len(boards)} specific boards"
    subject = "the board below" if len(boards) == 1 else "each board below"
    parts = [
        f"## Measured values for {noun}",
        "",
        f"For {subject}, these are the values the engine computes. Column"
        " heights are measured from the floor, so an empty column is 0 and a"
        " column whose topmost filled cell is in row 0 is 20.",
    ]
    for label, board in boards:
        parts += [
            "",
            f"### {label}",
            "",
            "```",
            render_board(board),
            "```",
            "",
            f"- column heights: `{list(board.column_heights())}`",
            f"- holes: `{holes(board)}`",
        ]
    return "\n".join(parts) + "\n"


class BoardSampler:
    """Captures the board at chosen piece counts.

    The feedback summary's own snapshots are the worst-holes board and the final
    one, and late in a losing game those are nearly the same ceiling-high mess:
    every column measures ~20 and the heights barely discriminate, so a
    miscounted height would be invisible in them. A counterexample needs boards
    whose structure varies, which means sampling early.
    """

    def __init__(self, at: tuple[int, ...]) -> None:
        self.at = at
        self.boards: dict[int, Board] = {}

    def __call__(self, game) -> None:  # noqa: ANN001 - duck-typed on Game
        if game.pieces_placed in self.at:
            self.boards[game.pieces_placed] = game.board


def sample_boards(
    source: str, seed: int, config: LoopConfig, at: tuple[int, ...] = (16,)
) -> list[tuple[str, Board]]:
    """Replay a function and grab the boards at the chosen piece counts."""
    sampler = BoardSampler(at=at)
    with ScoringSandbox(source) as sandbox:
        agent = StrategyAgent(sandbox)
        play_game(Game(seed=seed, max_pieces=config.max_pieces), agent, on_step=sampler)
    chosen: list[tuple[str, Board]] = []
    seen: set[Board] = set()
    for pieces in sorted(sampler.boards):
        board = sampler.boards[pieces]
        if board in seen:
            continue
        seen.add(board)
        chosen.append((f"after {pieces} pieces", board))
    return chosen[: len(at)]


def build_counterexample_prompt(
    config: LoopConfig, previous: Outcome, boards: list[tuple[str, Board]]
) -> str:
    """The control's prompt, plus the trace block. Everything else identical.

    It was not always so, and the first five generations collected with this
    script predate the fix. This function used to pass ``measurement_section=""``
    while the control's ``build_prompt`` passes ``MEASUREMENT_DECLARATION``, so
    the "counterexample" prompt also silently *dropped* a 418-character block --
    the one that names the measured quantities at every iteration, added in
    f840a10 precisely to stop a prompt change confounding a measured effect.
    Measured: 418 characters removed, 560 added, 978 characters differing, for a
    net of +142. Reporting that net as "a 142-char difference" made a two-block
    manipulation look like one addition.

    Keeping the declaration makes the contrast a single block again. A
    replication will therefore not reproduce the five collected generations
    byte-for-byte, and that is the correct trade: reproducing them exactly would
    mean preserving the confound.
    """

    feedback_section = (
        "## How your last attempt went\n\n"
        f"{feedback_text(previous, config)}\n\n"
        f"{trace_block(boards)}\n"
        "## The function you wrote\n\n"
        f"```python\n{previous.source}```\n\n"
        "Write an improved version below. You may keep whatever worked, "
        "change whatever did not, and restructure freely.\n"
    )
    return render(
        config.template,
        width=10,
        height=20,
        last_row=19,
        per_call_seconds=config.per_call_seconds,
        measurement_section=MEASUREMENT_DECLARATION if config.declare_metrics else "",
        feedback_section=feedback_section,
    )


def held_out(source: str, max_pieces: int) -> tuple[float, float, float]:
    """Mean score, mean pieces and mean holes over unseen seeds."""
    with ScoringSandbox(source) as sandbox:
        agent = StrategyAgent(sandbox)
        rows = [play_game(Game(seed=seed, max_pieces=max_pieces), agent) for seed in HELD_OUT_SEEDS]
    return (
        statistics.mean(r.score for r in rows),
        statistics.mean(r.pieces_placed for r in rows),
        statistics.mean(r.final_holes for r in rows),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-14b")
    parser.add_argument("--config", type=Path, default=Path("configs/models.yaml"))
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="first artifact number; raise it so a replication does not overwrite earlier runs",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--trace-at",
        type=int,
        nargs="+",
        default=[16],
        help="piece counts whose boards go in the trace block. Vary this: three runs on"
        " the same board probe generation variance, not whether the effect depends on"
        " which board is shown",
    )
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument("--function", type=Path, default=None, help="the function to revise")
    parser.add_argument(
        "--timeout",
        type=float,
        default=2400.0,
        help="per-call budget; this prompt can generate far longer than iteration 0",
    )
    args = parser.parse_args()

    # Retries are disabled deliberately. A local generation that exceeds its
    # budget will exceed it again, and the first attempt at this experiment spent
    # 60 of its 80 minutes on three pointless retries after a timeout.
    config = replace(
        load_model_config(args.config, args.model),
        timeout_seconds=args.timeout,
        max_retries=0,
    )
    loop_config = LoopConfig(
        model=config.name, train_seeds=(args.seed,), max_pieces=args.max_pieces
    )
    path = args.function or Path(f"runs/functions/noise/{config.name}-noise1.py")

    previous = play_function(path.read_text(), args.seed, loop_config)
    base = held_out(path.read_text(), args.max_pieces)
    print(f"model {config.name} ({config.model})")
    print(f"revising {path}")
    print(
        f"iteration 0 held-out: score {base[0]:.0f} pieces {base[1]:.1f} holes {base[2]:.1f}\n",
        flush=True,
    )

    trace_at = tuple(args.trace_at)
    boards = sample_boards(path.read_text(), args.seed, loop_config, at=trace_at)
    if len(boards) != len(trace_at):
        raise SystemExit(
            f"asked for boards at {trace_at} but the game only reached "
            f"{len(boards)} of them; the function blocks out early"
        )
    print("trace boards: " + ", ".join(label for label, _ in boards), flush=True)
    prompt = build_counterexample_prompt(loop_config, previous, boards)
    control = len(feedback_text(previous, loop_config))
    print(
        f"counterexample prompt {len(prompt)} chars "
        f"(the trace block adds roughly {len(prompt) - control - 3529} over the control)\n",
        flush=True,
    )

    out_dir = Path("runs/functions/counterexample")
    out_dir.mkdir(parents=True, exist_ok=True)
    # The board goes in the filename, because which board the trace showed is the
    # independent variable. The first three runs predate this and are named
    # `-counterexample{1,2,3}.py`; they all used piece 16.
    tag = "_".join(str(piece) for piece in trace_at)

    for index in range(args.start_index, args.start_index + args.runs):
        client = ModelClient(config)
        started = time.monotonic()
        response = client.complete([{"role": "user", "content": prompt}])
        elapsed = time.monotonic() - started
        try:
            source = extract_code(response.text)
        except Exception as error:  # noqa: BLE001 - an unparseable reply is a result
            print(f"run {index}: UNPARSEABLE ({error})", flush=True)
            continue

        (out_dir / f"{config.name}-counterexample-p{tag}-{index}.py").write_text(source)
        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        score, pieces, hole_count = held_out(source, args.max_pieces)
        # Whether the *original* broken line survived -- which is all a string
        # test can establish. It deliberately no longer reads "fixed": the
        # piece-8 run replaced that line with a differently broken hole count
        # that scans the wrong way (161 where the engine counts 17), and a
        # string test reported it as a change. Correctness has to be read from
        # the measured holes column beside it, where a working hole count drives
        # the held-out average down from ~86 and a broken one does not.
        survived = "heights[col] > row" in source
        print(
            f"run {index}: {digest}  {elapsed:.0f}s  out={client.usage.tokens_out}\n"
            f"         held-out: score {score:.0f} pieces {pieces:.1f} holes {hole_count:.1f}\n"
            f"         original hole line survived: {survived}  "
            f"(a change is not a fix; read the holes column)",
            flush=True,
        )

    print()
    print("CONTROL (outcome feedback only, already collected):")
    print("  revision A held-out score 130, revision B 85, against iteration 0's 110.")
    print("  Both kept `heights[col] > row` verbatim and changed only weights.")


if __name__ == "__main__":
    main()
