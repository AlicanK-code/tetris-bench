"""The shape of a logged run.

Two layers, deliberately not one flat dataclass.

:class:`GameResult` is what a finished game produced -- score, lines, and the
board features at the end and on average. It knows nothing about models, so the
baseline agents produce a complete record with no empty fields.

:class:`RunRecord` wraps a :class:`GameResult` with the model-side facts: which
model, which mode, which iteration of the improvement loop, and what the calls
cost in tokens, time and money. Baseline games simply have no ``RunRecord``.

They flatten to a single JSON object at write time, so the JSONL on disk is one
level deep and trivially loadable into a dataframe -- the layering is for the
code's benefit, not the file's.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tetris_bench.engine.game import GameOverCause
from tetris_bench.metrics import BoardStats


@dataclass(frozen=True)
class GameResult:
    """What one finished game produced.

    The averages are sampled after every placement rather than read off the
    final board, because a game that ends tall may have been played low for most
    of its length, and the reverse. The final board alone hides that.
    """

    agent: str
    seed: int
    agent_seed: int | None
    score: int
    lines_cleared: int
    pieces_placed: int
    cause: GameOverCause | None
    final_aggregate_height: int
    final_max_height: int
    final_bumpiness: int
    final_holes: int
    avg_max_height: float
    avg_bumpiness: float
    avg_holes: float

    @classmethod
    def from_game_stats(
        cls,
        *,
        agent: str,
        seed: int,
        agent_seed: int | None,
        score: int,
        lines_cleared: int,
        pieces_placed: int,
        cause: GameOverCause | None,
        final: BoardStats,
        samples: list[BoardStats],
    ) -> GameResult:
        """Build a result from the final board and the per-placement samples."""

        def mean(values: list[int]) -> float:
            return sum(values) / len(values) if values else 0.0

        return cls(
            agent=agent,
            seed=seed,
            agent_seed=agent_seed,
            score=score,
            lines_cleared=lines_cleared,
            pieces_placed=pieces_placed,
            cause=cause,
            final_aggregate_height=final.aggregate_height,
            final_max_height=final.max_height,
            final_bumpiness=final.bumpiness,
            final_holes=final.holes,
            avg_max_height=mean([s.max_height for s in samples]),
            avg_bumpiness=mean([s.bumpiness for s in samples]),
            avg_holes=mean([s.holes for s in samples]),
        )

    def as_dict(self) -> dict[str, Any]:
        """A flat dict, ready to be written as a line of JSONL."""
        return asdict(self)


@dataclass(frozen=True)
class ModelUsage:
    """What talking to a model cost for one game.

    Zeroed rather than optional: a strategy-mode game that made no calls at a
    given checkpoint really did use zero tokens, which is different from unknown.
    """

    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    invalid_outputs: int = 0
    sandbox_failures: int = 0
    # Retries are tallied apart from calls so cost-per-call stays meaningful
    # while provider flakiness is still visible. failed_calls counts logical
    # calls that never succeeded, which is different from a call that needed
    # two attempts and then worked.
    retries: int = 0
    failed_calls: int = 0


@dataclass(frozen=True)
class RunRecord:
    """One game played by one model at one iteration of the improvement loop."""

    game: GameResult
    model: str
    mode: str
    iteration: int
    usage: ModelUsage = field(default_factory=ModelUsage)
    #: Which independent chain this belongs to. Chains never see each other's
    #: functions, so a rising median across chains cannot be selection bias.
    chain: int = 0
    #: Hash of the scoring function played, so a row ties back to its artifact.
    function_sha: str = ""
    #: How many of the game's moves the function failed to separate. A function
    #: that discriminated on nothing scored zero for a mechanical reason rather
    #: than a strategic one, and the analysis has to be able to tell them apart.
    flat_moves: int = 0
    scored_moves: int = 0
    #: Mean gap between the best and worst candidate, and how often the choice
    #: was not simply the first candidate. Both were computed and discarded
    #: before; without them the decision-relevance question cannot be asked of
    #: an existing log.
    mean_spread: float = 0.0
    steering_moves: int = 0
    #: False when the function was rejected or crashed, so no game ran. Without
    #: this a rejection looks like a flawless game in a dataframe: zero holes,
    #: zero height, zero score.
    played: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Flatten to a single-level JSON object for JSONL."""
        return {
            "model": self.model,
            "mode": self.mode,
            "iteration": self.iteration,
            "chain": self.chain,
            "function_sha": self.function_sha,
            "flat_moves": self.flat_moves,
            "scored_moves": self.scored_moves,
            "mean_spread": self.mean_spread,
            "steering_moves": self.steering_moves,
            "played": self.played,
            **self.game.as_dict(),
            **asdict(self.usage),
        }
