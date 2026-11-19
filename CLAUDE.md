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
- Run it in a separate subprocess with a hard timeout (per call and per game).
- Do not allow imports, or allowlist pure modules only (e.g. `math`). Do not allow file, network or OS access.
- Validate the function's signature and return type, and treat exceptions or timeouts as a recorded failure, not a crash.
- Log every generated function to disk for later inspection.

As built, this is two independent layers:

1. **Static AST allowlist** (`sandbox.py`) rejects imports, private and dunder attribute access, and the builtins that reach outside the process — before anything runs. Not because a subprocess could not contain them, but because a rejected function fails instantly with a readable reason instead of burning a timeout.
2. **Containment** (`sandbox_worker.py`) runs the function in a separate interpreter under `-I`, importing no project module, with a small allowlist of builtins and `SIGALRM` bounding each call. Verified to hold on its own with layer 1 disabled: `open` and `__import__` are `NameError`s, `import` fails at load, boards are immutable tuples, and non-numeric or `NaN` returns are refused.

`math` is **pre-injected rather than importable**, so the one pure module a scoring function may want is available without permitting an import statement at all.

One worker per game, batched per piece: a game is ~500 pieces × ~34 placements, so a process per scoring call would mean 17,000 spawns and over eight minutes per game of pure process creation.

The function sees **plain data only** — boards as tuples of tuples of bool, placements as dicts — so no class, module or method of this project crosses into the sandbox.

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
│   ├── agents/         # random, heuristic, strategy (direct agent to come)
│   ├── prompts/        # versioned prompt templates + loader
│   ├── sandbox.py      # AST validation + host side of the sandbox
│   ├── sandbox_worker.py  # the isolated child; stdlib only, run by path
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
6. **Improvement loop**: feedback summary → revised function → replay, for N iterations over a fixed seed set.
7. **Direct agent**: baseline mode for comparison (small seed set only, as it is expensive).
8. **Analysis**: improvement curves per model, the size-ladder gap, tokens and seconds per point, a results table for the README.

Finish and test each milestone before starting the next.

## Metrics to log (per game, as JSONL)

model, mode, seed, iteration, score, lines cleared, pieces placed, final/avg max height, holes, bumpiness, cause of game over, invalid outputs / sandbox failures, model calls, tokens in/out, latency, estimated cost.

Derived: improvement per iteration, best-so-far curve, iterations to plateau, regression count, tokens per point, seconds per point.

Estimated cost stays in the schema and will read zero for every local run; it is there so a paid model could be added without a migration.

## Tech stack

- Python 3.11+, `uv` (or pip/venv) for environments
- `pytest` for tests, `ruff` for lint/format
- `openai` SDK (pointed at different base URLs for different providers)
- `pyyaml` for configs, `pandas` + `matplotlib` for analysis
- Local inference: Ollama or LM Studio on a MacBook (Apple Silicon, 32GB unified memory), so roughly 20–30B models at 4-bit quantisation at most. This is the only inference the project uses.

## Commands (update as they become real)

```bash
uv sync                         # install deps
uv run pytest                   # run tests
uv run ruff check . && uv run ruff format .
uv run tetris-bench play --agent heuristic --seed 1
uv run tetris-bench play --agent random --show-state --log runs/baseline.jsonl
uv sync --extra llm                                          # model client deps
uv run tetris-bench models                                   # validate model config
uv run tetris-bench strategy --model qwen3-4b --seed 1       # model writes a scorer
uv run tetris-bench loop --config configs/local-small.yaml   # not built yet
```

## Conventions

- Type hints everywhere; small, pure functions in the engine.
- The engine has zero dependencies on LLM code.
- Never commit API keys; read them from environment variables (`.env` is gitignored).
- Every experiment run is reproducible from its config file + seed list.
- Keep prompts in versioned template files, not inline strings, so prompt changes are traceable.

## Working with me

- I'm building Python fluency, so explain non-obvious design choices briefly and prefer clear code over clever code.
- Propose a plan before large changes; keep commits small and focused per milestone.
- Ask before adding new dependencies.
