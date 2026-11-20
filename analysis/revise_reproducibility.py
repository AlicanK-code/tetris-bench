"""Is a *revision* reproducible, or only a first attempt?

The sampling budget for the whole sweep rests on an untested transfer.
`noise_floor.py` established that `qwen3-14b` generates byte-identically across
five runs -- but it tested only the **iteration-0** prompt. Every iteration after
the first uses a prompt roughly twice as long, carrying a feedback summary, two
rendered boards and the previous function.

The project's own explanation for nondeterminism makes this a property of the
*(model, prompt)* pair, not of the model alone: divergence happens when a long
generation hits a near-tie that floating-point noise can flip, so a longer prompt
with a different generation length is a different experiment. Nothing licenses
assuming iteration-0 reproducibility carries over.

What rests on it: `chains=1` for the 14B. If a revision diverges, every rung
needs several chains, and the sweep multiplies by about five. Better to learn
that in half an hour than ten hours into a run.

Method: take a function already on disk, replay it to produce a genuine feedback
summary, build the real iteration-1 prompt, and generate the revision N times.

    uv run python analysis/revise_reproducibility.py --model qwen3-14b --runs 2
"""

from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path

from tetris_bench.agents.strategy import extract_code
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.config import load_model_config
from tetris_bench.loop import LoopConfig, build_prompt, play_function


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-14b")
    parser.add_argument("--config", type=Path, default=Path("configs/models.yaml"))
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument(
        "--function",
        type=Path,
        default=None,
        help="the previous function to revise (default: this model's noise-floor one)",
    )
    args = parser.parse_args()

    config = load_model_config(args.config, args.model)
    loop_config = LoopConfig(
        model=config.name, train_seeds=(args.seed,), max_pieces=args.max_pieces
    )

    path = args.function or Path(f"runs/functions/noise/{config.name}-noise1.py")
    if not path.exists():
        raise SystemExit(f"no previous function at {path}; pass --function")

    print(
        f"model {config.name} ({config.model}) - temperature {config.temperature}, "
        f"seed {config.seed}"
    )
    print(f"revising {path}\n", flush=True)

    # Replay it so the feedback is the real thing, not a fabrication.
    previous = play_function(path.read_text(), args.seed, loop_config)
    print(
        f"previous function: score={previous.score} "
        f"pieces={previous.result.pieces_placed if previous.result else 0}",
        flush=True,
    )

    prompt = build_prompt(loop_config, previous)
    first = build_prompt(loop_config, None)
    print(
        f"iteration-0 prompt {len(first)} chars; revision prompt {len(prompt)} chars "
        f"({len(prompt) / len(first):.1f}x)\n",
        flush=True,
    )

    rows = []
    for index in range(1, args.runs + 1):
        client = ModelClient(config)
        started = time.monotonic()
        response = client.complete([{"role": "user", "content": prompt}])
        elapsed = time.monotonic() - started
        try:
            source = extract_code(response.text)
        except Exception as error:  # noqa: BLE001 - an unparseable reply is a result
            print(f"run {index}: UNPARSEABLE ({error})", flush=True)
            rows.append(("unparseable", 0, 0, None))
            continue

        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        outcome = play_function(source, args.seed, loop_config)
        rows.append((digest, client.usage.tokens_out, len(response.reasoning), outcome.score))
        print(
            f"run {index}: {digest}  {elapsed:.0f}s  out={client.usage.tokens_out} "
            f"reasoning={len(response.reasoning)} score={outcome.score}",
            flush=True,
        )
        Path("runs/functions/revise").mkdir(parents=True, exist_ok=True)
        (Path("runs/functions/revise") / f"{config.name}-revise{index}.py").write_text(source)

    print(f"\n{'=' * 68}")
    digests = {row[0] for row in rows}
    scores = [row[3] for row in rows if row[3] is not None]
    print(f"distinct revisions : {len(digests)} of {len(rows)}")
    if scores:
        print(f"scores             : {scores}  spread {max(scores) - min(scores)}")
    print()
    # Text divergence and score divergence are different problems, and only the
    # second threatens the curve. Conflating them would either waste compute on
    # chains that cannot change a result, or hide real variance.
    spread = (max(scores) - min(scores)) if len(scores) > 1 else 0
    if len(digests) == 1:
        print("TEXT-REPRODUCIBLE. Iteration-0 reproducibility carries over to the")
        print("revise prompt on this rung, so chains=1 is justified.")
    elif spread == 0:
        print("TEXT DIVERGES, SCORE DOES NOT. The revisions differ as source but")
        print("score identically, so chains would add cost without changing any")
        print("result -- on this evidence. Note the sample is small: equal scores")
        print("from a handful of draws is weak evidence that the score is stable.")
        print("Raise --runs before relying on chains=1 for this rung.")
    else:
        print(f"SCORE DIVERGES by {spread}. The revise prompt is nondeterministic in")
        print("the way that matters. This rung needs several chains, and an")
        print("improvement smaller than the spread cannot be distinguished from it.")


if __name__ == "__main__":
    main()
