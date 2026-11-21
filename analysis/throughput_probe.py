"""Can this machine generate faster? Measured answer: no, not usefully.

A six-iteration five-chain sweep is 30 generations at about 655 seconds each,
which is 5.5 hours, and essentially all of it is token generation -- a full
held-out replay of 13 games takes under 7 seconds. So the only two levers are
fewer generations, which shrinks the experiment, or faster generation. This
script tested the second one, and the answer is that it is not available.

**Concurrency: 1.37x at four streams, not worth having.** Chains in the
improvement loop are independent by design, so they could run at once. Decode is
memory-bandwidth-bound, and a batch reads the weights once per step for every
stream in it, so concurrency can pay on this kind of workload. Here it barely
does:

    streams   wall s   tokens  agg tok/s  per-stream  speedup
          1     46.6      600       12.9        12.9    1.00x
          2     64.4      944       14.7         9.0    1.14x
          4    121.0    2,144       17.7         5.1    1.37x

Per-stream throughput collapses from 12.9 to 5.1 tok/s, which nearly cancels the
benefit of running four. 1.37x turns 5.5 hours into 4.0, and buying that 1.5
hours means a thread per chain and concurrent appends to the one JSONL the result
is read from -- new concurrency in the component whose output *is* the finding.
For an unattended overnight run, where 5.5 hours and 4.0 hours both finish before
morning, that is a bad trade. The loop stays sequential deliberately, and this is
the measurement behind that choice rather than an assumption.

**Context size: no effect.** Ollama serves this model with `-c 32768` while a run
needs about 15,500 tokens (a 1,533-token prompt plus the 14,000-token cap), so
17,000 tokens of KV cache are allocated and never used. Reclaiming them looked
like a free speedup. It is not: single stream, one slot, context as the only
variable, 32768 gave 12.5 tok/s and 16384 gave 10.3. There is no mechanism by
which a smaller allocation is *slower* for the same sequence length, so that is
run-to-run variance -- which also means the 12.9 measured here against the 9-11
seen in real runs was noise, not a finding. Between-run spread on this rig is
roughly 10 to 13 tok/s, and anything smaller than that is not measurable.

Needs a llama-server with more than one slot, which Ollama does not provide
(it launches `-np 1`, so concurrent requests queue and a probe against it shows
no gain for the wrong reason). Launch one from Ollama's own binary:

    /Applications/Ollama.app/Contents/Resources/llama-server \\
      --model ~/.ollama/models/blobs/sha256-<digest> \\
      --port 48080 --host 127.0.0.1 --no-webui --offline \\
      -c 65536 -np 4 --flash-attn auto -b 1024 -ub 1024 \\
      --no-jinja --chat-template chatml --keep 4

    uv run python analysis/throughput_probe.py
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request

from tetris_bench.agents.strategy import build_strategy_prompt

#: The real iteration-0 prompt, so prefill and context are representative.
PROMPT = build_strategy_prompt()


def one_request(url: str, seed: int, max_tokens: int, out: list[tuple[int, float]]) -> None:
    """Send one generation and record (tokens, seconds)."""
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.7,
            "seed": seed,
            "max_tokens": max_tokens,
            "frequency_penalty": 0.5,
        }
    ).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=1800) as response:
        payload = json.load(response)
    out.append((payload["usage"]["completion_tokens"], time.monotonic() - started))


def measure(url: str, streams: int, max_tokens: int) -> tuple[float, float, int, float]:
    """Run `streams` generations at once. Returns (wall, aggregate, tokens, per-stream)."""
    results: list[tuple[int, float]] = []
    threads = [
        threading.Thread(target=one_request, args=(url, 100 + i, max_tokens, results))
        for i in range(streams)
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.monotonic() - started

    tokens = sum(count for count, _ in results)
    per_stream = sum(count / seconds for count, seconds in results) / len(results)
    return wall, tokens / wall, tokens, per_stream


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:48080/v1/chat/completions")
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument(
        "--streams",
        type=int,
        nargs="+",
        default=[1, 2, 4],
        help="concurrency levels to test; each must be <= the server's slot count",
    )
    args = parser.parse_args()

    print(f"prompt {len(PROMPT)} chars, {args.max_tokens} output tokens per request\n")
    header = (
        f"{'streams':>8}{'wall s':>9}{'tokens':>9}{'agg tok/s':>11}{'per-stream':>12}{'speedup':>9}"
    )
    print(header)
    print("-" * len(header))

    baseline = 0.0
    for streams in args.streams:
        wall, aggregate, tokens, per_stream = measure(args.url, streams, args.max_tokens)
        baseline = baseline or aggregate
        print(
            f"{streams:>8}{wall:>9.1f}{tokens:>9,}"
            f"{aggregate:>11.1f}{per_stream:>12.1f}{aggregate / baseline:>8.2f}x"
        )

    print(
        "\nRead the per-stream column, not just the speedup: concurrency that halves\n"
        "each stream to gain a third overall is rarely worth the complexity."
    )


if __name__ == "__main__":
    main()
