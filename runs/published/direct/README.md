# The milestone 7 direct-mode demonstration

One game: `qwen3-14b` choosing placements one at a time, one model call per
piece, piece seed 1, 20-piece budget, 3 h 44 m. Cited by
[direct-mode-costs-800x-and-plays-like-random.md](../../../docs/findings/direct-mode-costs-800x-and-plays-like-random.md)
and the top-level README.

| file | what it is |
|---|---|
| `direct.jsonl` | The run record. One row, `mode: "direct"`, carrying the score, holes, height, `invalid_outputs`, token counts and total latency. |
| `run.log` | The CLI's own output: final board, summary, and the per-piece token and latency figures as printed. |
| `inference-server-timings.log` | The inference server's request log for the 20 calls, which is where the **per-piece** latency spread comes from. Durations are rounded to 10 s, so they sum to 13,311 s against the client-measured 13,440.9 s. |

**The model's 20 replies are not here, because `direct` mode does not save
them.** `strategy` mode writes a `.json` per generation with the prompt,
reasoning and raw reply, which is what makes those findings auditable; the
direct agent keeps only a bounded sample of *invalid* replies for the CLI to
print, and this game produced none. Every claim in the write-up rests on the
aggregate row rather than on reply text, but a future direct arm should log the
replies — at one call per piece the artifact would be large, which is probably
why it does not.
