"""Playing a game to the end and recording what happened.

One function and one record. Every later milestone needs to run a game and keep
the result -- the baselines now, per-game statistics in milestone 3, sandboxed
model scorers in milestone 5, and the improvement loop in milestone 6 -- so this
is the single place a game is driven from.

:class:`GameResult` covers the game-side metrics the project logs per game. The
model-side fields (tokens, latency, cost, sandbox failures) belong to the run
layer that calls a model, and are added when that exists, so nothing here
depends on LLM code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tetris_bench.agents.base import Agent
from tetris_bench.engine.game import Game, GameOverCause
from tetris_bench.metrics import bumpiness, holes, max_height


@dataclass(frozen=True)
class GameResult:
    """What one finished game produced.

    ``avg_max_height`` is sampled after every placement rather than taken at the
    end, because a game that ends tall may still have been played low for most of
    its length -- and the reverse. The final board alone hides that.
    """

    agent: str
    seed: int
    agent_seed: int | None
    score: int
    lines_cleared: int
    pieces_placed: int
    cause: GameOverCause | None
    final_max_height: int
    avg_max_height: float
    final_holes: int
    final_bumpiness: int

    def as_dict(self) -> dict[str, Any]:
        """A plain dict, ready to be written as a line of JSONL."""
        return asdict(self)


def play_game(game: Game, agent: Agent, agent_seed: int | None = None) -> GameResult:
    """Play ``game`` to completion with ``agent`` and return the result."""
    heights: list[int] = []

    while not game.over:
        game.step(agent.choose(game))
        heights.append(max_height(game.board))

    return GameResult(
        agent=agent.name,
        seed=game.seed,
        agent_seed=agent_seed,
        score=game.score,
        lines_cleared=game.lines_cleared,
        pieces_placed=game.pieces_placed,
        cause=game.cause,
        final_max_height=max_height(game.board),
        avg_max_height=sum(heights) / len(heights) if heights else 0.0,
        final_holes=holes(game.board),
        final_bumpiness=bumpiness(game.board),
    )
