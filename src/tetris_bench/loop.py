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

**Training seeds are fed back; evaluation seeds are held out.** A function plays
every training sequence and the feedback aggregates across them, so the signal is
about the function rather than one sequence. It is then played on a disjoint set
of evaluation sequences it never informed, and those rows are what a curve should
be read from. This matters because a single sequence is a noisy estimate: a fixed
function varies 85-348% across unseen seeds, and the project has already recorded
a training-seed score of 400 that turned out to be a function's luckiest case out
of twenty-one rather than its typical one (held-out mean 110).

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
)
from tetris_bench.clients.client import ModelClient
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.feedback import (
    MultiSeedFeedback,
    SnapshotCollector,
    build_feedback,
)
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

TEMPLATE = "strategy_v3"

#: Named at EVERY iteration, including the first. These quantities are what the
#: feedback summary reports, and if they were introduced only at iteration 1 then
#: the first step of every curve would confound "the model learned from its
#: failure" with "the model was handed a vocabulary it did not have". The 4B's
#: iteration-0 trace never mentioned surface shape at all, so that confound was
#: real rather than hypothetical. Declaring the vocabulary up front makes it a
#: constant treatment instead of a step change.
#:
#: Note what this names and what it does not: the *quantities* are named, their
#: *definitions* are not. A model still has to work out what a hole is -- which
#: is the thing every rung has so far got wrong.
MEASUREMENT_DECLARATION = """\
## How your function will be judged

It will play one game, and you will be told: the score, lines cleared, pieces
placed, how the game ended, the number of holes left on the board, the height of
the tallest column, and how uneven the surface was. You will also be shown the
board at the end and at its worst point.

Those are the quantities measured. What they mean, and which of them matter, is
for you to work out.
"""


@dataclass(frozen=True)
class LoopConfig:
    """One sweep: a model, its seed splits, and how many iterations and chains."""

    model: str
    #: Sequences whose outcomes are fed back to the model. Several, so a revision
    #: cannot be tuned to one sequence.
    train_seeds: tuple[int, ...] = (1, 2, 17)
    #: Sequences the model never sees the results of. The curve is read from
    #: these. Playing them is free -- under a second per game -- so there is no
    #: reason to be stingy.
    eval_seeds: tuple[int, ...] = tuple(range(1000, 1010))
    iterations: int = 6
    #: One chain is right for a reproducible rung; a nondeterministic one needs
    #: several before a difference between iterations is meaningful.
    chains: int = 1
    max_pieces: int = 500
    per_call_seconds: float = 1.0
    #: One template for every iteration. The feedback block is empty at
    #: iteration 0 and populated afterwards, so the feedback is the *only*
    #: difference between the first prompt and the second. Previously iteration 0
    #: used `strategy_v2` and later ones `revise_v1`, which differed in several
    #: ways at once -- including dropping the board-orientation note that every
    #: rung has struggled with -- so the direction of the prompt change was
    #: unknown and tangled up with the measured effect.
    template: str = TEMPLATE
    #: Name the measured quantities at iteration 0 as well. See
    #: MEASUREMENT_DECLARATION.
    declare_metrics: bool = True
    log_path: Path = Path("runs/loop.jsonl")
    functions_dir: Path = Path("runs/functions")
    #: Shown to the model for scale. The heuristic reference on these seeds.
    reference_score: int | None = 21600


@dataclass(frozen=True)
class Position:
    """One unit of work: a chain and an iteration.

    No seed: a position now plays every training sequence, so the seed is not
    part of what identifies a unit of work.
    """

    chain: int
    iteration: int

    def stem(self, model: str) -> str:
        return f"{model}-chain{self.chain}-iter{self.iteration}"


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


@dataclass
class MultiOutcome:
    """One function played across several sequences."""

    source: str
    per_seed: dict[int, Outcome] = field(default_factory=dict)
    rejected: bool = False
    crashed: bool = False
    reason: str = ""

    @property
    def outcomes(self) -> list[Outcome]:
        return [self.per_seed[seed] for seed in sorted(self.per_seed)]

    @property
    def results(self) -> list[GameResult]:
        return [o.result for o in self.outcomes if o.result is not None]

    @property
    def mean_score(self) -> float:
        results = self.results
        return sum(r.score for r in results) / len(results) if results else 0.0

    @property
    def worst(self) -> Outcome | None:
        """The outcome of the lowest-scoring game, where the failure is clearest."""
        playable = [o for o in self.outcomes if o.result is not None]
        if not playable:
            return None
        return min(playable, key=lambda o: (o.result.score, o.result.pieces_placed))

    @property
    def diagnostics(self) -> StrategyDiagnostics:
        """Diagnostics pooled over every game."""
        pooled = StrategyDiagnostics()
        for outcome in self.outcomes:
            pooled.moves += outcome.diagnostics.moves
            pooled.flat_moves += outcome.diagnostics.flat_moves
            pooled.unplayable += outcome.diagnostics.unplayable
            pooled.spread_total += outcome.diagnostics.spread_total
            pooled.steering_moves += outcome.diagnostics.steering_moves
        return pooled

    @property
    def sandbox_failures(self) -> int:
        return sum(o.sandbox_failures for o in self.outcomes)

    @property
    def sandbox_errors(self) -> list[str]:
        errors: list[str] = []
        for outcome in self.outcomes:
            errors.extend(outcome.sandbox_errors)
        return errors[:10]


def play_on_seeds(source: str, seeds: tuple[int, ...], config: LoopConfig) -> MultiOutcome:
    """Play one function on every given sequence.

    A rejection or a crash is a property of the source, not of a sequence, so the
    first such result short-circuits the rest rather than repeating it.
    """
    multi = MultiOutcome(source=source)
    for seed in seeds:
        outcome = play_function(source, seed, config)
        if outcome.rejected or outcome.crashed:
            return MultiOutcome(
                source=source,
                rejected=outcome.rejected,
                crashed=outcome.crashed,
                reason=outcome.reason,
            )
        multi.per_seed[seed] = outcome
    return multi


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


def feedback_text(outcome: Outcome | MultiOutcome, config: LoopConfig) -> str:
    """What the model is shown about its previous attempt.

    Accepts a single game (used by the analysis scripts) or a set of games across
    training sequences (used by the loop).
    """
    if isinstance(outcome, MultiOutcome) and not (outcome.rejected or outcome.crashed):
        worst = outcome.worst
        collector = worst.collector if worst else None
        final_board = worst.final_board if worst else None
        snapshots = (
            collector.snapshots(final_board)
            if collector is not None and final_board is not None
            else []
        )
        return MultiSeedFeedback(
            results=outcome.results,
            diagnostics=outcome.diagnostics,
            snapshots=snapshots,
            sandbox_failures=outcome.sandbox_failures,
            sandbox_errors=outcome.sandbox_errors,
            reference_score=config.reference_score,
        ).render()

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


def build_prompt(config: LoopConfig, previous: Outcome | MultiOutcome | None) -> str:
    """Render the prompt for one iteration.

    Identical at every iteration apart from the feedback block, which is empty
    on the first. That is the whole point: if the template also changed, a rise
    from iteration 0 to 1 could not be attributed to the feedback.
    """
    if previous is None:
        feedback_section = ""
    else:
        feedback_section = (
            "## How your last attempt went\n\n"
            f"{feedback_text(previous, config)}\n\n"
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


def generate(
    client: ModelClient,
    config: LoopConfig,
    position: Position,
    previous: Outcome | MultiOutcome | None,
) -> GeneratedFunction:
    """Ask the model for a function, first attempt or revision alike."""
    from tetris_bench.agents.strategy import extract_code

    prompt = build_prompt(config, previous)
    response = client.complete([{"role": "user", "content": prompt}])
    return GeneratedFunction(
        source=extract_code(response.text),
        model=response.model,
        prompt=prompt,
        raw_reply=response.text,
        reasoning=response.reasoning,
        iteration=position.iteration,
    )


def completed_positions(
    log_path: Path, model: str, train_seeds: tuple[int, ...] = ()
) -> set[tuple[int, int]]:
    """Which (chain, iteration) positions this log already holds in full.

    A position counts as done only when every training sequence has a row. A run
    killed part-way through a position would otherwise be skipped on resume with
    some of its games missing, and its feedback would then be built from an
    incomplete set.
    """
    if not Path(log_path).exists():
        return set()
    seen: dict[tuple[int, int], set[int]] = {}
    for row in read_records(log_path):
        if row.get("model") != model or row.get("mode") != "strategy":
            continue
        if row.get("split", "train") != "train":
            continue
        key = (row.get("chain", 0), row.get("iteration", -1))
        seen.setdefault(key, set()).add(row.get("seed", -1))
    required = set(train_seeds)
    if not required:
        return set(seen)
    return {key for key, seeds in seen.items() if required <= seeds}


def positions(config: LoopConfig) -> Iterator[Position]:
    """Every unit of work in the sweep, in execution order.

    Chain-major, because iterations within a chain are strictly sequential while
    chains are independent.
    """
    for chain in range(config.chains):
        for iteration in range(config.iterations):
            yield Position(chain, iteration)


def _sha(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()[:12]


def _record(
    position: Position,
    config: LoopConfig,
    outcome: Outcome,
    usage: ModelUsage,
    seed: int,
    split: str,
) -> RunRecord:
    result = outcome.result or empty_result("strategy", seed)
    return RunRecord(
        split=split,
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
    done = completed_positions(config.log_path, config.model, config.train_seeds)

    previous: Outcome | MultiOutcome | None = None
    current_chain: int | None = None

    for position in positions(config):
        if position.chain != current_chain:
            current_chain, previous = position.chain, None

        if (position.chain, position.iteration) in done:
            path = config.functions_dir / f"{position.stem(config.model)}.py"
            if not path.exists():
                # Falling through would append a second set of records for a
                # position the log already holds, and any per-position analysis
                # would double-count it. The log and the saved functions have to
                # agree, so say so plainly instead.
                raise RuntimeError(
                    f"{config.log_path} has records for {position.stem(config.model)} "
                    f"but {path} is missing, so its feedback cannot be reconstructed. "
                    f"Restore the file, or start a fresh log to re-run from scratch."
                )
            previous = play_on_seeds(path.read_text(), config.train_seeds, config)
            say(f"skip  {position.stem(config.model)} (already in the log)")
            continue

        client.reset_usage()
        try:
            generated = generate(client, config, position, previous)
        except StrategyError as error:
            # The reply never arrived as usable Python, so there is nothing for
            # the model to act on. Log it as an invalid output, then carry the
            # last function that actually played: replacing `previous` here would
            # send the next iteration an empty code block while still numbering
            # it a continuation of this chain.
            failure = Outcome(
                source="",
                rejected=True,
                reason=f"your reply could not be read as Python: {error}",
            )
            _log_position(config, position, failure, client.usage, "train")
            say(
                f"iter {position.iteration} chain {position.chain}: "
                f"UNPARSEABLE REPLY (keeping the previous function)"
            )
            if previous is None:
                previous = failure
            continue

        generated.save(config.functions_dir, position.stem(config.model))
        multi = play_on_seeds(generated.source, config.train_seeds, config)

        if multi.rejected or multi.crashed:
            failure = Outcome(
                source=generated.source,
                rejected=multi.rejected,
                crashed=multi.crashed,
                reason=multi.reason,
            )
            _log_position(config, position, failure, client.usage, "train")
            label = "REJECTED" if multi.rejected else "CRASHED"
            say(f"iter {position.iteration} chain {position.chain}: {label}")
            previous = multi
            continue

        _log_multi(config, position, multi, client.usage, "train")

        # Evaluation games cost under a second each and the model never sees
        # their outcomes, so this is the curve's variable at no generation cost.
        evaluation = play_on_seeds(generated.source, config.eval_seeds, config)
        _log_multi(config, position, evaluation, ModelUsage(), "eval")

        say(
            f"iter {position.iteration} chain {position.chain}: "
            f"train mean {multi.mean_score:.0f}  "
            f"eval mean {evaluation.mean_score:.0f}  "
            f"({len(config.eval_seeds)} held-out seeds)"
        )
        previous = multi


def _log_position(
    config: LoopConfig,
    position: Position,
    outcome: Outcome,
    usage: ModelUsage,
    split: str,
) -> None:
    """Log one failed position: a row per training seed, usage counted once."""
    for index, seed in enumerate(config.train_seeds):
        append_record(
            config.log_path,
            _record(position, config, outcome, usage if index == 0 else ModelUsage(), seed, split),
        )


def _log_multi(
    config: LoopConfig,
    position: Position,
    multi: MultiOutcome,
    usage: ModelUsage,
    split: str,
) -> None:
    """Log every game of a position.

    The generation's usage is attributed to the first row only. Repeating it on
    each row would multiply a position's token count by the number of seeds.
    """
    for index, seed in enumerate(sorted(multi.per_seed)):
        append_record(
            config.log_path,
            _record(
                position,
                config,
                multi.per_seed[seed],
                usage if index == 0 else ModelUsage(),
                seed,
                split,
            ),
        )
