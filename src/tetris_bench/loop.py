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

import functools
import hashlib
import statistics
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tetris_bench.agents.strategy import (
    GeneratedFunction,
    StrategyAgent,
    StrategyDiagnostics,
    StrategyError,
    build_strategy_prompt,
)
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.transport import ModelError
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import DEFAULT_MAX_PIECES, Game
from tetris_bench.feedback import (
    MultiSeedFeedback,
    SnapshotCollector,
    build_feedback,
)
from tetris_bench.jsonl import append_record, read_records
from tetris_bench.metrics import BoardStats
from tetris_bench.records import GameResult, ModelUsage, RunRecord
from tetris_bench.runner import play_game
from tetris_bench.sandbox import (
    SandboxCrashed,
    SandboxGameDeadline,
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
    #: Deferred to the engine's default rather than restated, so the budget has
    #: one definition. See the note there on why score is a censored measure.
    max_pieces: int = DEFAULT_MAX_PIECES
    per_call_seconds: float = 1.0
    #: Wall-clock budget for one game, or None for no limit. Defaults to the
    #: sandbox's own default rather than restating a number here, so the budget
    #: has one definition -- the same reason `max_pieces` defers to the engine.
    per_game_seconds: float | None = SandboxLimits.per_game_seconds
    #: One template for every iteration. The feedback block is empty at
    #: iteration 0 and populated afterwards, so the feedback is the *only*
    #: difference between the first prompt and the second. Previously iteration 0
    #: used `strategy_v2` and later ones `revise_v1`, which differed in several
    #: ways at once -- including dropping the board-orientation note that every
    #: rung has struggled with -- so the direction of the prompt change was
    #: unknown and tangled up with the measured effect.
    #: Show every earlier attempt in the chain, not just the last one. Off by
    #: default: every published run here was measured without it, and turning it
    #: on silently would make a new run incomparable with those. See
    #: :func:`history_section` for why its scores are training scores.
    history: bool = False

    template: str = TEMPLATE
    #: Name the measured quantities at iteration 0 as well. See
    #: MEASUREMENT_DECLARATION.
    declare_metrics: bool = True
    #: Base model seed for chain 0; chain k generates under ``model_seed + k``.
    #: ``None`` leaves every chain on whatever the client is configured with,
    #: which is the old behaviour and is what the fakes in the test suite use.
    #: The CLI fills this in from the model config, so a real sweep always gets
    #: independent chains. See :func:`model_seed_for`.
    model_seed: int | None = None
    log_path: Path = Path("runs/loop.jsonl")
    functions_dir: Path = Path("runs/functions")
    #: Shown to the model for scale, as "a good scoring function scores around
    #: N". `None` computes it by playing the hand-written heuristic on this
    #: run's own training seeds at this run's own budget; an int overrides that.
    #:
    #: It used to be the literal 21600, which was the heuristic's score at a
    #: 500-piece budget and became wrong the moment the budget moved to 2000,
    #: where the same agent scores around 87,000. The feedback says "survives
    #: the full piece budget and scores around N", so a stale N understates the
    #: target by a factor of four -- and unlike the printed references in
    #: analysis/, this one goes into the prompt the model reads.
    reference_score: int | None = None


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
    #: A crash that was specifically the whole-game time budget running out.
    #: Kept apart from a wedge because the two need different feedback: a wedge
    #: is usually a loop that never ends, while this function terminates on
    #: every call and is simply too slow to finish a game.
    deadline: bool = False
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
    deadline: bool = False
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

    A **rejection** is a property of the source: the AST validator refuses it
    without reference to any board, so the first rejection short-circuits the
    rest rather than repeating a verdict that cannot change.

    A **crash** is not. The host's batch deadline depends on how many placements
    a board offers and how long the function takes on them, so a wedge is
    board-dependent and therefore sequence-dependent. This used to discard every
    game already played, which did two bad things: it logged a function that had
    played two sequences well as a row of zeroes, and it told the model "no game
    could be completed and there are no results to report" -- untrue, and it
    withheld the only evidence available for diagnosing a board-dependent wedge.
    So a crash now stops the remaining sequences but keeps what finished.
    """
    multi = MultiOutcome(source=source)
    for seed in seeds:
        outcome = play_function(source, seed, config)
        if outcome.rejected:
            return MultiOutcome(source=source, rejected=True, reason=outcome.reason)
        if outcome.crashed:
            multi.crashed = True
            multi.deadline = outcome.deadline
            multi.reason = outcome.reason
            break
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
    limits = SandboxLimits(
        per_call_seconds=config.per_call_seconds,
        per_game_seconds=config.per_game_seconds,
    )
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
    except SandboxGameDeadline as error:
        # Caught before SandboxCrashed, which it subclasses, so the slow-function
        # case is labelled rather than reported as a wedge.
        return Outcome(source=source, crashed=True, deadline=True, reason=str(error))
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
    # Report the games that finished whenever there are any, even if a later
    # sequence then wedged. Only a rejection -- where nothing ran at all -- has
    # no results to show. The crash is appended as a note below.
    if isinstance(outcome, MultiOutcome) and outcome.results and not outcome.rejected:
        worst = outcome.worst
        collector = worst.collector if worst else None
        final_board = worst.final_board if worst else None
        snapshots = (
            collector.snapshots(final_board)
            if collector is not None and final_board is not None
            else []
        )
        rendered = MultiSeedFeedback(
            results=outcome.results,
            diagnostics=outcome.diagnostics,
            snapshots=snapshots,
            sandbox_failures=outcome.sandbox_failures,
            sandbox_errors=outcome.sandbox_errors,
            reference_score=_resolved_reference(config),
        ).render()
        if outcome.crashed:
            # Still a symptom, not a diagnosis: it says the run stopped and on
            # which sequence, not why. That a wedge happened on some boards and
            # not others is information the model needs and can act on.
            what = "ran out of time for a whole game" if outcome.deadline else "stopped responding"
            rendered += (
                "\n\n## One sequence stopped early\n\n"
                f"- after the games above, your function {what} and "
                f"that game was abandoned: {outcome.reason}\n"
                "- the remaining sequences were not played, so the table above "
                "is shorter than usual"
            )
        return rendered

    if outcome.rejected:
        return (
            "## Your code was rejected before it could run\n\n"
            f"{outcome.reason}\n\n"
            "Nothing was played, so there are no results to report. Fix the "
            "problem above and try again."
        )

    if outcome.deadline:
        # Deliberately a symptom and not a diagnosis, like every other part of
        # the feedback: it reports that the game ran out of time, not what in
        # the function is slow. Saying "a loop that does not terminate" here --
        # the wedge advice below -- would be an actively wrong diagnosis, since
        # a function that hits this one returns from every call it is given.
        return (
            "## Your function ran out of time before a game could finish\n\n"
            f"{outcome.reason}\n\n"
            "Every individual call returned, so this is not a loop that never "
            "ends: the function is simply doing too much work per placement, "
            "and a game is thousands of placements. Scoring one board should be "
            "a few passes over 200 cells. Look for work repeated per placement "
            "that could be done once, and for nested scans over the board."
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
        reference_score=_resolved_reference(config),
    ).render()


def history_section(history: Sequence[Outcome | MultiOutcome]) -> str:
    """Every earlier attempt in this chain, oldest first, with what it scored.

    The single-step loop shows a model only its last function and how that one
    went, so it cannot tell whether its previous change helped -- which is a
    plausible cause of the "reweights rather than debugs" behaviour this project
    measures. This renders the trajectory instead, in the spirit of Reflexion
    and OPRO.

    **The scores here are training scores, not held-out ones.** Showing a model
    its held-out results would destroy the only property that makes the curve
    worth reading: the evaluation sequences are the ones it never sees. A
    history arm built on held-out feedback would measure a model tuning against
    the test set, so it reports the same training outcomes the model was already
    shown at the time -- only now it can see all of them at once.

    Attempts that never played -- a rejected or unparseable generation -- are
    listed with their reason rather than a score, because "this produced
    nothing" is exactly the kind of step a model should be able to see it took.
    """
    if not history:
        return ""
    blocks = []
    for index, outcome in enumerate(history):
        if isinstance(outcome, MultiOutcome) and outcome.results:
            pieces = sum(r.pieces_placed for r in outcome.results)
            score = sum(r.score for r in outcome.results)
            rate = score / pieces if pieces else 0.0
            headline = f"{score:,} points over {pieces:,} pieces ({rate:.2f} per piece)"
        else:
            headline = outcome.reason.strip() or "it produced no playable function"
        source = outcome.source.strip()
        body = f"```python\n{source}\n```\n" if source else "_no function was produced_\n"
        blocks.append(f"### Attempt {index} - {headline}\n\n{body}")
    return (
        "## Everything you have tried in this chain so far\n\n"
        "Oldest first, on the training sequences. Use it to judge whether your "
        "last change helped.\n\n" + "\n".join(blocks) + "\n"
    )


def build_prompt(
    config: LoopConfig,
    previous: Outcome | MultiOutcome | None,
    history: Sequence[Outcome | MultiOutcome] = (),
) -> str:
    """Render the prompt for one iteration.

    Identical at every iteration apart from the feedback block, which is empty
    on the first. That is the whole point: if the template also changed, a rise
    from iteration 0 to 1 could not be attributed to the feedback.
    """
    if previous is None:
        feedback_section = ""
    else:
        # An unparseable reply leaves no source to show. Printing the heading
        # with an empty code block under it tells the model it wrote something
        # blank, which is both false and unactionable.
        wrote = (
            f"## The function you wrote\n\n```python\n{previous.source}```\n\n"
            if previous.source.strip()
            else ""
        )
        feedback_section = (
            "## How your last attempt went\n\n"
            f"{feedback_text(previous, config)}\n\n"
            f"{wrote}"
            "Write an improved version below. You may keep whatever worked, "
            "change whatever did not, and restructure freely.\n"
        )

    # Delegated rather than rendered here, so that one-shot `strategy` mode and
    # this cannot render the same template differently. They did once.
    if config.history and history:
        # Prepended inside the feedback section rather than added to the
        # template, so `strategy_v3` is byte-identical in both arms and the only
        # difference between them is this block.
        feedback_section = history_section(history) + "\n" + feedback_section

    return build_strategy_prompt(
        width=10,
        height=20,
        per_call_seconds=config.per_call_seconds,
        template=config.template,
        declare_metrics=config.declare_metrics,
        feedback_section=feedback_section,
    )


def generate(
    client: ModelClient,
    config: LoopConfig,
    position: Position,
    previous: Outcome | MultiOutcome | None,
    history: Sequence[Outcome | MultiOutcome] = (),
) -> GeneratedFunction:
    """Ask the model for a function, first attempt or revision alike."""
    from tetris_bench.agents.strategy import extract_code

    prompt = build_prompt(config, previous, history)
    seed = model_seed_for(config.model_seed, position.chain)
    response = client.complete([{"role": "user", "content": prompt}], seed=seed)
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


def unplayed_positions(log_path: Path, model: str) -> set[tuple[int, int]]:
    """Positions the log holds whose function never played a game.

    An unparseable reply is logged as an invalid output and the loop moves on
    *without* saving a ``.py`` file, because the reply contained no Python to
    save. On resume such a position counts as complete but has no artifact, and
    the skip branch's replay would raise ``RuntimeError`` -- bricking the resume
    of a multi-hour run until someone hand-edited the JSONL. These positions
    need skipping without a replay, which matches the live branch: nothing
    played, so there is nothing to carry forward.

    The genuine log/artifact disagreement that ``RuntimeError`` was written for
    is still an error; this only excuses the case the log itself explains.
    """
    if not Path(log_path).exists():
        return set()
    played: dict[tuple[int, int], bool] = {}
    for row in read_records(log_path):
        if row.get("model") != model or row.get("mode") != "strategy":
            continue
        key = (row.get("chain", 0), row.get("iteration", -1))
        played[key] = played.get(key, False) or bool(row.get("played", True))
    return {key for key, ever_played in played.items() if not ever_played}


def logged_eval_seeds(log_path: Path, model: str) -> dict[tuple[int, int], set[int]]:
    """Which evaluation sequences each position already has rows for.

    ``completed_positions`` counts only training rows, so a run killed between
    the training and evaluation writes leaves a position marked done with its
    held-out games missing or half-written. That is permanent: resume skips it
    and never fills the gap, and the curve -- which is read from evaluation rows
    -- then carries either an unmarked zero or a mean over three seeds pooled
    with means over ten. Replaying the saved function to top up the missing
    seeds costs under a second and needs no model call.
    """
    if not Path(log_path).exists():
        return {}
    seeds: dict[tuple[int, int], set[int]] = {}
    for row in read_records(log_path):
        if row.get("model") != model or row.get("mode") != "strategy":
            continue
        if row.get("split") != "eval":
            continue
        key = (row.get("chain", 0), row.get("iteration", -1))
        seeds.setdefault(key, set()).add(row.get("seed", -1))
    return seeds


def positions(config: LoopConfig) -> Iterator[Position]:
    """Every unit of work in the sweep, in execution order.

    Chain-major, because iterations within a chain are strictly sequential while
    chains are independent.
    """
    for chain in range(config.chains):
        for iteration in range(config.iterations):
            yield Position(chain, iteration)


def model_seed_for(base: int | None, chain: int) -> int | None:
    """The model seed chain ``chain`` generates under.

    Chains exist so that a rising median across independent samples cannot be
    selection bias. At temperature 0 with one seed that premise is false: every
    chain sends an identical request and gets an identical function back, which
    was measured -- chain 0 and chain 1 produced byte-identical hashes, and
    `chain_spread` was exactly 0. Several chains then cost several times the GPU
    hours and buy one sample.

    Offsetting by the chain index fixes that without giving up reproducibility:
    each chain is still deterministic and still reproducible from the config, and
    chain 0 keeps the configured seed, so a single-chain run is bit-for-bit what
    it was before this existed.

    A model configured with no seed keeps none, since offsetting nothing is
    nothing.
    """
    return None if base is None else base + chain


@functools.cache
def heuristic_reference(seeds: tuple[int, ...], max_pieces: int) -> int:
    """Mean score of the hand-written heuristic, as a scale for the model.

    Computed rather than quoted, because the only honest value depends on the
    budget: the heuristic does not die inside 2000 pieces on most seeds, so its
    score there is the budget times its rate. Hard-coding one number means the
    prompt silently lies the next time the budget changes, which is exactly what
    happened.

    Cached on its arguments: a run asks for this once per position but the
    answer cannot change within a run, and the games are a second or two each.
    """
    from tetris_bench.agents.heuristic import heuristic_agent

    scores = [
        play_game(Game(seed=seed, max_pieces=max_pieces), heuristic_agent()).score for seed in seeds
    ]
    return round(sum(scores) / len(scores)) if scores else 0


def _resolved_reference(config: LoopConfig) -> int | None:
    """The configured reference, or the measured one when none is set."""
    if config.reference_score is not None:
        return config.reference_score
    if not config.train_seeds:
        return None
    return heuristic_reference(tuple(config.train_seeds), config.max_pieces)


def _sha(source: str) -> str:
    """Short digest of a generated function, or `""` when there is no function.

    The empty case is not hypothetical: a position whose reply could not be
    parsed, or whose call failed outright, is logged with `source=""`. Hashing
    that returns `e3b0c44298fc` -- the digest of the empty string -- which looks
    exactly like a real function id in the log, is identical across every such
    row, and would make two unrelated failures appear to share a function.
    `""` is what the field already defaults to for "no function", so it says
    the right thing and needs no schema change.
    """
    if not source:
        return ""
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
    unplayed = unplayed_positions(config.log_path, config.model)
    have_eval = logged_eval_seeds(config.log_path, config.model)

    previous: Outcome | MultiOutcome | None = None
    history: list[Outcome | MultiOutcome] = []
    current_chain: int | None = None

    for position in positions(config):
        if position.chain != current_chain:
            # A chain is an independent lineage, so its history starts empty.
            current_chain, previous, history = position.chain, None, []

        if (position.chain, position.iteration) in done:
            key = (position.chain, position.iteration)
            path = config.functions_dir / f"{position.stem(config.model)}.py"

            # The artifact decides, not the `played` flag. A *rejected* or
            # *crashed* position has every row flagged unplayed and yet has a
            # saved file, because the source is written before it is played. An
            # earlier version checked `unplayed` first and so skipped the replay
            # for those, leaving the next iteration to be built from a stale
            # `previous` -- or from `None`, which sends a bare iteration-0 prompt
            # numbered as a later iteration. The same chain then produced a
            # different prompt depending on whether it had been resumed, which
            # is the confound f840a10 was written to remove.
            if not path.exists():
                if key in unplayed:
                    # An unparseable reply held no Python to save, so the log
                    # itself explains the missing file. Nothing played, so leave
                    # `previous` alone, exactly as the live branch does.
                    say(f"skip  {position.stem(config.model)} (logged as an invalid output)")
                    continue
                # A genuine log/artifact disagreement. Falling through would
                # append a second set of records for a position the log already
                # holds, and any per-position analysis would double-count it.
                raise RuntimeError(
                    f"{config.log_path} has records for {position.stem(config.model)} "
                    f"but {path} is missing, so its feedback cannot be reconstructed. "
                    f"Restore the file, or start a fresh log to re-run from scratch."
                )
            source = path.read_text()
            previous = play_on_seeds(source, config.train_seeds, config)
            history.append(previous)

            # Top up any held-out games the log is missing. A kill between the
            # training and evaluation writes would otherwise leave this position
            # permanently short, and the curve is read from these rows.
            missing = tuple(s for s in config.eval_seeds if s not in have_eval.get(key, set()))
            if missing:
                replayed = play_on_seeds(source, missing, config)
                _log_multi(config, position, replayed, ModelUsage(), "eval")
                # The count of games actually recovered, not of games attempted.
                # A function that wedges on a particular sequence wedges on it
                # every time, so a top-up can legitimately recover nothing and
                # must not claim otherwise on each resume.
                recovered = len(replayed.per_seed)
                note = (
                    f"recovered {recovered} of {len(missing)} missing held-out game(s)"
                    if recovered
                    else f"could not recover {len(missing)} held-out game(s): {replayed.reason}"
                )
                say(f"skip  {position.stem(config.model)} (already in the log; {note})")
            else:
                say(f"skip  {position.stem(config.model)} (already in the log)")
            continue

        client.reset_usage()
        try:
            generated = generate(client, config, position, previous, history)
        except ModelError as error:
            # The call itself never came back -- a timeout, or a provider error
            # the client gave up on. Previously this propagated and killed the
            # run, which is the worst available outcome: every position already
            # finished stays on disk, but the tokens and seconds just spent are
            # lost, nothing records *why* the run stopped, and a resume has to
            # rediscover it. One rung burned 80 minutes and three attempts this
            # way before `max_tokens` was capped to make a runaway generation
            # return instead of hang.
            #
            # So treat it the same as an unusable reply: log the position as a
            # failure with its usage, keep the last function that played, and
            # carry on to the next position. `max_retries` has already been
            # exhausted inside the client by this point, so there is nothing
            # left to retry here.
            failure = Outcome(
                source="",
                rejected=True,
                reason=f"the model call failed: {error}",
            )
            _log_position(config, position, failure, client.usage, "train")
            say(
                f"iter {position.iteration} chain {position.chain}: "
                f"CALL FAILED ({error}) (keeping the previous function)"
            )
            if previous is None:
                previous = failure
            continue
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

        if multi.rejected or (multi.crashed and not multi.per_seed):
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
            history.append(multi)
            continue

        _log_multi(config, position, multi, client.usage, "train")

        if multi.crashed:
            # Some sequences finished and a later one wedged. Logging the whole
            # position as zeros -- which is what this did -- discarded real
            # games and left the log contradicting the feedback the model was
            # shown, which truthfully reported them. So the finished games are
            # logged above and only the sequences that never ran are zeroed
            # here, and the held-out games below still get played.
            stopped = Outcome(source=generated.source, crashed=True, reason=multi.reason)
            for seed in config.train_seeds:
                if seed not in multi.per_seed:
                    append_record(
                        config.log_path,
                        _record(position, config, stopped, ModelUsage(), seed, "train"),
                    )
            say(
                f"iter {position.iteration} chain {position.chain}: CRASHED after "
                f"{len(multi.per_seed)} of {len(config.train_seeds)} sequences - {multi.reason}"
            )

        # Evaluation games cost under a second each and the model never sees
        # their outcomes, so this is the curve's variable at no generation cost.
        evaluation = play_on_seeds(generated.source, config.eval_seeds, config)
        _log_multi(config, position, evaluation, ModelUsage(), "eval")
        if len(evaluation.results) < len(config.eval_seeds):
            # The curve is read from these rows, so a short set has to be
            # visible rather than averaged quietly. A rerun tops it up from the
            # saved artifact; see logged_eval_seeds.
            say(
                f"      WARNING: {len(evaluation.results)} of "
                f"{len(config.eval_seeds)} held-out games logged"
                f"{' - ' + evaluation.reason if evaluation.reason else ''}"
            )

        say(
            f"iter {position.iteration} chain {position.chain}: "
            f"train mean {multi.mean_score:.0f}  "
            f"eval mean {evaluation.mean_score:.0f}  "
            f"({len(config.eval_seeds)} held-out seeds)"
        )
        previous = multi
        history.append(multi)


def summarise_run(log_path: Path | str, model: str, statistic: str = "median") -> str:
    """Describe a finished sweep in a few lines, read back from its own log.

    Deliberately reads the log rather than accumulating totals during the run:
    the log is the run's only source of truth, and a resumed sweep that skipped
    most of its positions would otherwise report only the handful it replayed.

    The held-out figure is a *median* across chains by default. That is not a
    neutral choice and the caller should know it: on the first five-chain sweep
    the median rose 670 to 1410 while the mean fell 2226 to 1270, because one
    chain started at 9590 and collapsed. Both summarise the same five numbers.
    """
    if statistic not in ("median", "mean"):
        raise ValueError(f"statistic must be 'median' or 'mean', not {statistic!r}")

    rows = [r for r in read_records(log_path) if r.get("model") == model]
    if not rows:
        return f"{model}: no records in {log_path}"

    held_out: dict[int, dict[int, list[int]]] = {}
    positions_seen: set[tuple[int, int]] = set()
    tokens_out = 0
    failures = 0
    for row in rows:
        positions_seen.add((row.get("chain", 0), row.get("iteration", 0)))
        failures += row.get("failed_calls") or 0
        if row.get("split") == "eval":
            by_chain = held_out.setdefault(row.get("iteration", 0), {})
            by_chain.setdefault(row.get("chain", 0), []).append(row.get("score") or 0)
        elif row.get("seed") == rows[0].get("seed"):
            # Usage is logged per position, repeated on each of its rows, so
            # counting one seed's rows counts each generation once.
            tokens_out += row.get("tokens_out") or 0

    lines = [f"{model}: {len(positions_seen)} generations, {tokens_out:,} tokens out"]

    # One mean per chain per iteration, which is the unit everything below uses.
    chain_means: dict[int, list[float]] = {
        iteration: [statistics.fmean(scores) for scores in by_chain.values()]
        for iteration, by_chain in sorted(held_out.items())
    }
    if chain_means:
        pick = statistics.median if statistic == "median" else statistics.fmean
        curve = {iteration: pick(means) for iteration, means in chain_means.items()}
        first, last = min(curve), max(curve)
        chains = max(len(means) for means in chain_means.values())
        lines.append(
            f"held-out {statistic} it{first} {curve[first]:,.0f} "
            f"-> it{last} {curve[last]:,.0f} ({chains} chain(s))"
        )

        # The noise bar, where there is more than one chain to compare: if this
        # is larger than the movement reported above, the movement is not news.
        spreads = [max(means) - min(means) for means in chain_means.values() if len(means) > 1]
        if spreads:
            lines.append(f"widest spread between chains {max(spreads):,.0f}")

    if failures:
        lines.append(f"{failures} failed model call(s)")
    return "\n".join(lines)


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
