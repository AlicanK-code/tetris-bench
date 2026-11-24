# CLAUDE.md — Tetris LLM Benchmark (working name: `tetris-bench`)

## What this project is

A benchmark that measures how well LLMs **improve at Tetris across repeated attempts**, not just how well they play once.

Each model plays the same seeded piece sequences, gets feedback on how it did, revises its strategy, and plays again. The headline result is each model's **improvement curve**: who learns fastest, who plateaus, and who regresses after a revision.

Secondary angle: a **capability-ladder analysis** across local models of increasing size (roughly 4B to 30B, all on one MacBook). Does the improvement loop let a small model close on a larger one?

**Everything runs locally. No paid APIs.** The client supports cloud providers and that path is tested, but no planned run uses one. The practical consequence is that dollar cost is always zero, so the headline cost measures are **tokens and wall-clock seconds**, not dollars.

This is a portfolio project. Code should be readable, well structured and easy to explain in an interview.

### Prior work (for context, not to copy)
- **lmgame-Bench** (UCSD, 2025): Tetris is one of several games; the authors found vision input hurts and a harness helps.
- **TetrisBench** (a16z, 2026): direct move-picking failed; it worked once the model wrote a *scoring function* that ranks legal placements.
- Our differentiator: the **iterative self-improvement loop** and how it is measured.

## Key design decisions

1. **Text/grid state, not screenshots.** The board is passed as a text grid plus structured metadata (current piece, next pieces). Vision is out of scope.
   - **No hold piece.** Hold roughly doubles the branching factor per turn and adds a state dimension for a model to reason about, for a benchmark whose subject is the quality of a scoring function rather than the breadth of the move vocabulary. Additive to add later if wanted.
   - Filled cells render as `#` by default, dropping piece identity: Tetris is Markovian in occupancy, so which piece filled a cell cannot change the best move. `show_pieces=True` keeps the letters for feedback snapshots and debugging.
2. **Placement-based, not real-time.** No gravity timing. Each turn the agent chooses a final placement (rotation + column) from the list of legal placements. This removes latency from the problem.
3. **Deterministic and seeded.** Piece generation uses a seeded 7-bag randomiser. Every model plays the same seeds, so results are directly comparable.
4. **Two play modes:**
   - `direct`: the model picks a placement each turn (expensive; used as a baseline).
   - `strategy`: the model writes a Python `score(board, placement) -> float` function. The engine evaluates every legal placement with it and picks the best. The model is called only between games or at checkpoints. **This is the main mode.**
5. **Improvement loop.** After each game the model receives a feedback summary (score, lines, holes, max height, cause of death, a few key board snapshots) along with its previous function, and returns a revised one. Run N iterations per model per seed set.
6. **One client interface for every model.** Local models (Ollama / LM Studio) and cloud models are all called through an OpenAI-compatible chat API. The provider is just config (base URL, model name, API key).

## Safety: model-generated code

`strategy` mode executes code written by a model. It must never run in-process with full privileges.
- Run it in a separate subprocess with a hard timeout on every call, on every
  piece, and on the whole game.
- Do not allow imports, or allowlist pure modules only (e.g. `math`). Do not allow file, network or OS access.
- Validate the function's signature and return type, and treat exceptions or timeouts as a recorded failure, not a crash.
- Log every generated function to disk for later inspection.

As built, this is two independent layers:

1. **Static AST allowlist** (`sandbox.py`) rejects imports, private and dunder attribute access, and the builtins that reach outside the process — before anything runs. Not because a subprocess could not contain them, but because a rejected function fails instantly with a readable reason instead of burning a timeout.
2. **Containment** (`sandbox_worker.py`) runs the function in a separate interpreter under `-I`, importing no project module, with a small allowlist of builtins and `SIGALRM` bounding each call. Verified to hold on its own with layer 1 disabled: `open` and `__import__` are `NameError`s, `import` fails at load, boards are immutable tuples, and non-numeric or `NaN` returns are refused.

`math` is **pre-injected rather than importable**, so the one pure module a scoring function may want is available without permitting an import statement at all.

One worker per game, batched per piece: a game is up to 2000 pieces × ~34 placements, so a process per scoring call would mean 68,000 spawns and over half an hour per game of pure process creation.

The function sees **plain data only** — boards as tuples of tuples of bool, placements as dicts — so no class, module or method of this project crosses into the sandbox.

### Three time bounds, one per level

- **Per call**, `SIGALRM` at `per_call_seconds` (1.0s). It raises a `BaseException` subclass deliberately, so a `try/except Exception` inside the scoring function cannot swallow its own timeout.
- **Per piece**, a host-side deadline of `max(30s, per_call_seconds × placements + 10s)` — about 44s for a typical 34-placement piece. The floor matters: a flat 30s would kill a worker behaving exactly as the per-call budget allows.
- **Per game**, `per_game_seconds` (300s), checked before each batch. `None` disables it, for deliberately long replays where a long game is the point.

The third one exists because the first two do not imply it. A function that merely spends its full second on every placement, never looping, could run `2000 pieces × 34 placements × 1s` — about **19 hours** — entirely within the rules, and an unattended sweep would simply appear to hang. Bounding the call and the piece does not bound the game.

300s is roughly a thousand times a real game: measured on the size ladder, 728 sandboxed games took about 92 seconds between them. A budget a plausible function could compete with would be a measurement rather than a safety net.

Two details that are load-bearing:

**`SandboxGameDeadline` subclasses `SandboxCrashed`.** Every caller already treats a crash as "this game is over, record a failure, keep the sweep running", which is the right response here too — so the deadline cannot escape through a handler nobody added. The distinct type is for telling them apart afterwards.

**It is checked between batches, not enforced inside one.** Cutting a batch short would kill a worker behaving exactly as allowed, which is the mistake `per_batch_seconds` was widened to a floor to avoid, and it would surface as a wedge rather than the deadline it is. So the real bound is the budget plus at most one batch — 344s at the defaults — and the feedback for a deadline deliberately does *not* repeat the wedge advice about non-terminating loops, which would be an actively wrong diagnosis for a function that returns from every call.

## Planned structure

```
tetris-bench/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── configs/            # model + experiment configs (YAML)
├── src/tetris_bench/
│   ├── engine/         # board, pieces, rotation, line clears, 7-bag RNG, legal placements
│   ├── render.py       # board/state/placements -> text for prompts
│   ├── metrics.py      # holes, height, bumpiness, BoardStats snapshot
│   ├── records.py      # GameResult (game-side) + RunRecord (model-side)
│   ├── jsonl.py        # append/read run records
│   ├── runner.py       # play_game(game, agent) -> GameResult
│   ├── clients/        # OpenAI-compatible client, provider config
│   ├── agents/         # random, heuristic, strategy, direct
│   ├── prompts/        # versioned prompt templates + loader
│   ├── sandbox.py      # AST validation + host side of the sandbox
│   ├── sandbox_worker.py  # the isolated child; stdlib only, run by path
│   ├── feedback.py     # finished game -> feedback summary (symptoms only)
│   ├── loop.py         # improvement loop orchestration
│   └── cli.py          # entry points
├── runs/               # outputs: JSONL logs, generated functions (gitignored)
├── analysis/           # notebooks/scripts for curves + tables
└── tests/
```

## Build order (milestones)

1. **Engine**: pieces, rotations, collision, line clears, seeded 7-bag, legal-placement enumeration, game-over detection. Fully unit tested. No LLMs yet.
2. **Baselines**: a random agent and a hand-written heuristic agent (classic weights: aggregate height, holes, bumpiness, lines). These sanity-check the engine and give reference scores.
3. **Rendering + metrics**: text grid output and per-game stats.
4. **Model client**: one OpenAI-compatible client and config for local (Ollama/LM Studio) and cloud providers. Track tokens, latency and cost per call.
5. **Strategy agent + sandbox**: prompt the model for a scoring function, run it safely, play a game. *Done.*
6. **Improvement loop**: feedback summary → revised function → replay, for N iterations over a fixed seed set. *Done.*
   - **Independent chains.** On a nondeterministic rung, several samples per iteration are needed before a difference means anything — the 30B showed a 1,700-point spread between two runs of the same request. Each chain iterates on its own function and never sees another's, so a rising median across chains cannot be selection bias. Carrying best-of-N forward would manufacture a curve from noise.
   - **Feedback is symptoms, not diagnoses**: score, lines, holes, height, cause of death, board snapshots and the prior function. The model must diagnose its own bug, because that is the ability being measured. The one exception is mechanical: when a function scored every candidate identically, the summary says so, since "you scored 0" cannot distinguish a bad strategy from inert arithmetic.
   - **Resumable by replay, no state file.** Records append as games finish and functions are written to disk; a rerun reads the log, skips completed positions, and replays the saved function to regenerate its feedback in under a second. One source of truth instead of a checkpoint that can drift.
   - **Training seeds are fed back; evaluation seeds are held out.** A function plays every training sequence and the feedback aggregates across them, so a revision cannot be tuned to one sequence. It is then replayed on a disjoint set of evaluation sequences whose outcomes the model never sees, and **the curve is read from those rows** (`split` in the log). This matters because a single sequence is a noisy estimate: a fixed, deterministic function varies 85–348% across unseen seeds, and a training-seed score of 400 turned out to be a function's luckiest case out of twenty-one (held-out mean 110). Evaluation games cost under a second each, so this is free.
   - **Chains per rung is not established.** `qwen3-14b` is reproducible on the *iteration-0* prompt but **not** on the revise prompt, which is 1.5× longer — two revisions of the same function gave two different sources, though both scored the same. No rung is text-reproducible for revisions. `chains=1` for the 14B currently rests on score stability from two samples. See `docs/findings/`.
7. **Direct agent**: baseline mode for comparison. *Done.*
   - **One demonstration game, not an arm.** Measured at **672 s and 6,444
     output tokens per piece**, which is 64-822x `strategy` mode depending on
     whether a generation is charged against one game or the ~900 pieces it is
     actually replayed over. A full 2,000-piece game would be 15.4 days, so a
     powered version — several seeds, several rungs — is weeks of wall clock for
     a baseline whose purpose is to be beaten.
   - **The reply is an index into the enumerated legal placements**, so every
     option is legal by construction. That is deliberately generous: it isolates
     *can you choose well* from *can you emit a well-formed move*, and the 14B
     answered all 20 calls with a valid index while playing inside the random
     distribution. Without the index design that result would have been
     indistinguishable from a formatting failure.
   - **A malformed answer is never rescued.** It is counted in
     `invalid_outputs` and the engine plays index 0 — arbitrary but
     deterministic. Falling back to the heuristic would let a model that never
     emits a valid answer score like a competent one.
8. **Analysis**: improvement curves per model, the size-ladder gap, tokens and seconds per point, a results table for the README.

Finish and test each milestone before starting the next.

## Metrics to log (per game, as JSONL)

model, mode, seed, iteration, score, lines cleared, pieces placed, final/avg max height, holes, bumpiness, cause of game over, invalid outputs / sandbox failures, model calls, tokens in/out, latency, estimated cost.

Derived: improvement per iteration, best-so-far curve, iterations to plateau, regression count, tokens per point, seconds per point.

**The headline measure is points per piece, not total score.** A total is censored by the piece budget — a game that hits the cap is cut off rather than finished — so it is a lower bound, and the project's best function is censored in 8 of 10 games. A rate has no such failure mode and is empirically budget-independent: the heuristic measures 43.2–43.5 points per piece at 500, 2,000, 20,000 and 50,000 pieces alike. Defined as total points over total pieces, which is what the baseline's own 43.5 already is. Totals stay in the schema and are reported beside the rate, because survival is a separate thing to know; "per point" in the derived metrics above therefore means per point of *rate*.

Estimated cost stays in the schema and will read zero for every local run; it is there so a paid model could be added without a migration.

## Tech stack

- Python 3.11+, `uv` (or pip/venv) for environments
- `pytest` for tests, `ruff` for lint/format
- `openai` SDK (pointed at different base URLs for different providers)
- `pyyaml` for configs, `pandas` + `matplotlib` for analysis
- Local inference: Ollama or LM Studio on a MacBook (Apple Silicon, 32GB unified memory), so roughly 20–30B models at 4-bit quantisation at most. This is the only inference the project uses.

## Commands (update as they become real)

**Install with `--all-extras`.** `uv sync` resolves the environment to exactly
what is asked for, so `uv sync --extra analysis` **uninstalls** the `llm` extra —
following the two extras as separate lines leaves the model client missing and
the loop failing at import. Both extras are needed on the same machine, because
a run is played and then plotted.

```bash
uv sync --all-extras            # install everything; see the note above
uv run pytest                   # run tests
uv run ruff check . && uv run ruff format .
uv run tetris-bench play --agent heuristic --seed 1
uv run tetris-bench play --agent random --show-state --log runs/baseline.jsonl
uv run tetris-bench models                                   # validate model config
uv run tetris-bench strategy --model qwen3-4b --seed 1       # model writes a scorer
uv run tetris-bench loop --model qwen3-14b --iterations 6 --chains 3   # the loop
uv run tetris-bench direct --model qwen3-14b --seed 1 --max-pieces 20  # 1 call/piece
uv run python analysis/curves.py                             # improvement curves
uv run python analysis/plots.py                              # figures
uv run python analysis/held_out.py                           # replay on unseen seeds
uv run python analysis/null_arm.py --runs 0                  # build prompts, no GPU
uv run python analysis/zeros_rate.py                         # dead-function proportion
uv run python analysis/placement_diff.py                     # decisions a revision changed
```

## Conventions

- Type hints everywhere; small, pure functions in the engine.
- The engine has zero dependencies on LLM code.
- Never commit API keys; read them from environment variables (`.env` is gitignored).
- Every experiment run is reproducible from its config file + seed list.
- Keep prompts in versioned template files, not inline strings, so prompt changes are traceable.
