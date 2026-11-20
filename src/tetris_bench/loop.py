"""The improvement loop: feedback, revise, replay, repeat.

This is the project's differentiator. A model writes a scoring function, the
engine plays a game with it, the model is shown how that went and writes a
revision. Repeat N times. What comes out is an improvement curve.

Three decisions shape this module.

**Independent chains.** On a nondeterministic rung, several samples per iteration
are needed before a difference means anything -- the 30B showed a 1,700-point
spread between two runs of the *same* request. Each chain iterates on its own
function and never sees another chain's work, so the median curve across chains
cannot be selection bias. Carrying the best-of-N forward instead would have
produced a rising curve from noise alone, which is the exact artefact the whole
exercise is trying to avoid.

**Feedback is symptoms, not diagnoses** -- see :mod:`tetris_bench.feedback`.

**Resumable by replay, with no state file.** Every game appends a record to a
JSONL log as it finishes, and every function is written to disk. On restart the
log says which positions are done; the previous function is read back from disk
and *replayed* to regenerate its feedback, which costs under a second because a
500-piece game is fast. That leaves one source of truth instead of a checkpoint
file that can disagree with the log.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from tetris_bench.agents.strategy import (
    GeneratedFunction,
    StrategyAgent,
    StrategyDiagnostics,
    StrategyError,
    request_scoring_function,
)
from tetris_bench.clients.client import ModelClient
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.feedback import SnapshotCollector, build_feedback
from tetris_bench.jsonl import append_record, read_records
from tetris_bench.metrics import BoardStats
from tetris_bench.prompts import render
from tetris_bench.records import GameResult, ModelUsage, RunRecord
from tetris_bench.runner import play_game
from tetris_bench.sandbox import (
    SandboxCrashed,
    SandboxLimits,
    SandboxValidationError,
    ScoringSandbox,
)

INITIAL_TEMPLATE = "strategy_v2"
REVISE_TEMPLATE = "revise_v1"


@dataclass(frozen=True)
class LoopConfig:
    """One sweep: a model, a seed set, and how many iterations and chains."""

    model: str
    seeds: tuple[int, ...] = (1,)
    iterations: int = 6
    #: One chain is right for a reproducible rung; a nondeterministic one needs
    #: several before a difference between iterations is meaningful.
    chains: int = 1
    max_pieces: int = 500
    per_call_seconds: float = 1.0
    initial_template: str = INITIAL_TEMPLATE
    revise_template: str = REVISE_TEMPLATE
    log_path: Path = Path("runs/loop.jsonl")
    functions_dir: Path = Path("runs/functions")
    #: Shown to the model for scale. The heuristic reference on these seeds.
    reference_score: int | None = 21600


@dataclass(frozen=True)
class Position:
    """One unit of work: a seed, a chain, an iteration."""

    seed: int
    chain: int
    iteration: int

    def stem(self, model: str) -> str:
        return f"{model}-seed{self.seed}-chain{self.chain}-iter{self.iteration}"


@dataclass
class Outcome:
    """What happened when a function was played."""

    source: str
    rejected: bool = False
    #: The function ran but wedged or killed its worker, so no game finished.
    #: Distinct from ``rejected``, which means it never started.
    crashed: bool = False
    reason: str = ""
    result: GameResult | None = None
    diagnostics: StrategyDiagnostics = field(default_factory=StrategyDiagnostics)
    final_board: Board | None = None
    collector: SnapshotCollector | None = None
    sandbox_failures: int = 0
    sandbox_errors: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return self.result.score if self.result else 0


def empty_result(agent: str, seed: int) -> GameResult:
    """A zero result, for a function that was rejected before it could play."""
    return GameResult.from_game_stats(
        agent=agent,
        seed=seed,
        agent_seed=None,
        score=0,
        lines_cleared=0,
        pieces_placed=0,
        cause=None,
        final=BoardStats(0, 0, 0, 0),
        samples=[],
    )


def play_function(source: str, seed: int, config: LoopConfig) -> Outcome:
    """Run one scoring function for a whole game, or record why it could not."""
    limits = SandboxLimits(per_call_seconds=config.per_call_seconds)
    try:
        with ScoringSandbox(source, limits=limits) as sandbox:
            agent = StrategyAgent(sandbox)
            game = Game(seed=seed, max_pieces=config.max_pieces)
            collector = SnapshotCollector()
            result = play_game(game, agent, on_step=collector)
            return Outcome(
                source=source,
                result=result,
                diagnostics=agent.diagnostics,
                final_board=game.board,
                collector=collector,
                sandbox_failures=sandbox.failures,
                sandbox_errors=list(sandbox.errors),
            )
    except SandboxValidationError as error:
        return Outcome(source=source, rejected=True, reason=str(error))
    except SandboxCrashed as error:
        # The worker died or stopped answering. This must not end the sweep: one
        # bad function would otherwise cost every remaining seed and chain, and
        # the loop's whole purpose is unattended multi-hour runs.
        return Outcome(source=source, crashed=True, reason=str(error))


def feedback_text(outcome: Outcome, config: LoopConfig) -> str:
    """What the model is shown about its previous attempt."""
    if outcome.rejected:
        return (
            "## Your code was rejected before it could run\n\n"
            f"{outcome.reason}\n\n"
            "Nothing was played, so there are no results to report. Fix the "
            "problem above and try again."
        )

    if outcome.crashed:
        return (
            "## Your function stopped responding and the game was abandoned\n\n"
            "It used up the time budget for a whole batch of placements, so no "
            "game could be completed and there are no results to report.\n\n"
            "The usual cause is a loop that does not terminate. Note that "
            "catching exceptions broadly will not rescue you from the time "
            "limit: make sure every loop has a bound that is reached."
        )

    assert outcome.result is not None and outcome.final_board is not None
    return build_feedback(
        result=outcome.result,
        diagnostics=outcome.diagnostics,
        final_board=outcome.final_board,
        collector=outcome.collector,
        sandbox_failures=outcome.sandbox_failures,
        sandbox_errors=outcome.sandbox_errors,
        reference_score=config.reference_score,
    ).render()


def completed_positions(log_path: Path, model: str) -> set[tuple[int, int, int]]:
    """Which (seed, chain, iteration) triples this log already holds."""
    if not Path(log_path).exists():
        return set()
    done: set[tuple[int, int, int]] = set()
    for row in read_records(log_path):
        if row.get("model") == model and row.get("mode") == "strategy":
            done.add((row.get("seed", -1), row.get("chain", 0), row.get("iteration", -1)))
    return done


def positions(config: LoopConfig) -> Iterator[Position]:
    """Every unit of work in the sweep, in execution order.

    Seed-major, then chain, then iteration -- because iterations within a chain
    are strictly sequential, while chains and seeds are independent.
    """
    for seed in config.seeds:
        for chain in range(config.chains):
            for iteration in range(config.iterations):
                yield Position(seed, chain, iteration)


def _sha(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()[:12]


def _record(
    position: Position, config: LoopConfig, outcome: Outcome, usage: ModelUsage
) -> RunRecord:
    result = outcome.result or empty_result("strategy", position.seed)
    return RunRecord(
        game=result,
        model=config.model,
        mode="strategy",
        iteration=position.iteration,
        chain=position.chain,
        function_sha=_sha(outcome.source),
        flat_moves=outcome.diagnostics.flat_moves,
        scored_moves=outcome.diagnostics.moves,
        mean_spread=outcome.diagnostics.mean_spread,
        steering_moves=outcome.diagnostics.steering_moves,
        played=not (outcome.rejected or outcome.crashed),
        usage=ModelUsage(
            model_calls=usage.model_calls,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
            latency_seconds=usage.latency_seconds,
            estimated_cost_usd=usage.estimated_cost_usd,
            invalid_outputs=1 if outcome.rejected else 0,
            # A crash produced no per-placement tally, so record at least one
            # failure rather than logging a clean-looking zero-score game.
            sandbox_failures=max(outcome.sandbox_failures, 1 if outcome.crashed else 0),
            retries=usage.retries,
            failed_calls=usage.failed_calls,
        ),
    )


def run_loop(
    client: ModelClient,
    config: LoopConfig,
    on_progress: object = print,
) -> None:
    """Run the sweep, appending a record per game and skipping completed work."""
    say = on_progress if callable(on_progress) else (lambda _m: None)
    done = completed_positions(config.log_path, config.model)

    previous: Outcome | None = None
    current_chain: tuple[int, int] | None = None

    for position in positions(config):
        chain_key = (position.seed, position.chain)
        if chain_key != current_chain:
            current_chain, previous = chain_key, None

        if (position.seed, position.chain, position.iteration) in done:
            # Already played. Replay the saved function so the next iteration has
            # its feedback, which costs well under a second.
            path = config.functions_dir / f"{position.stem(config.model)}.py"
            if not path.exists():
                # Falling through here would append a second record for a
                # position the log already holds, and any per-position analysis
                # would double-count it. The log and the saved functions have to
                # agree, so say so plainly instead.
                raise RuntimeError(
                    f"{config.log_path} has a record for {position.stem(config.model)} "
                    f"but {path} is missing, so its feedback cannot be reconstructed. "
                    f"Restore the file, or start a fresh log to re-run from scratch."
                )
            previous = play_function(path.read_text(), position.seed, config)
            say(f"skip  {position.stem(config.model)} (already in the log)")
            continue

        client.reset_usage()
        try:
            if previous is None:
                generated = request_scoring_function(
                    client,
                    per_call_seconds=config.per_call_seconds,
                    template=config.initial_template,
                    iteration=position.iteration,
                )
            else:
                generated = _request_revision(client, config, position, previous)
        except StrategyError as error:
            # CLAUDE.md lists invalid outputs as a per-game metric, so this has
            # to leave a row behind rather than silently skipping the position.
            outcome = Outcome(
                source="",
                rejected=True,
                reason=f"your reply could not be read as Python: {error}",
            )
            append_record(config.log_path, _record(position, config, outcome, client.usage))
            say(
                f"iter {position.iteration} seed {position.seed} "
                f"chain {position.chain}: UNPARSEABLE REPLY"
            )
            previous = outcome
            continue

        generated.save(config.functions_dir, position.stem(config.model))
        outcome = play_function(generated.source, position.seed, config)
        append_record(config.log_path, _record(position, config, outcome, client.usage))

        if outcome.rejected:
            say(f"iter {position.iteration} seed {position.seed} chain {position.chain}: REJECTED")
        elif outcome.crashed:
            say(f"iter {position.iteration} seed {position.seed} chain {position.chain}: CRASHED")
        else:
            say(
                f"iter {position.iteration} seed {position.seed} "
                f"chain {position.chain}: score={outcome.score} "
                f"pieces={outcome.result.pieces_placed if outcome.result else 0} "
                f"holes={outcome.result.final_holes if outcome.result else 0}"
            )
        previous = outcome


def _request_revision(
    client: ModelClient, config: LoopConfig, position: Position, previous: Outcome
) -> GeneratedFunction:
    """Ask for a revision, given how the previous attempt played."""
    prompt = render(
        config.revise_template,
        feedback=feedback_text(previous, config),
        previous_source=previous.source,
        width=10,
        height=20,
        last_row=19,
        per_call_seconds=config.per_call_seconds,
    )
    response = client.complete([{"role": "user", "content": prompt}])
    from tetris_bench.agents.strategy import extract_code

    return GeneratedFunction(
        source=extract_code(response.text),
        model=response.model,
        prompt=prompt,
        raw_reply=response.text,
        reasoning=response.reasoning,
        iteration=position.iteration,
    )
