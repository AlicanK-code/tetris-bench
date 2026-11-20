"""Playing a game to the end and recording what happened.

One function. Every later milestone needs to run a game and keep the result --
the baselines now, sandboxed model scorers in milestone 5, the improvement loop
in milestone 6 -- so this is the single place a game is driven from.

The record types live in :mod:`tetris_bench.records`; this module only produces
them.
"""

from __future__ import annotations

from collections.abc import Callable

from tetris_bench.agents.base import Agent
from tetris_bench.engine.game import Game
from tetris_bench.metrics import BoardStats, board_stats
from tetris_bench.records import GameResult


def play_game(
    game: Game,
    agent: Agent,
    agent_seed: int | None = None,
    on_step: Callable[[Game], None] | None = None,
) -> GameResult:
    """Play ``game`` to completion with ``agent`` and return the result.

    Board features are sampled after every placement so the result can report
    averages over the whole game, not just the state it ended in.

    ``on_step`` is called after each placement. It exists so the improvement loop
    can collect board snapshots for a feedback summary without reimplementing
    this loop, which would be a second place for the rules to drift.
    """
    samples: list[BoardStats] = []

    while not game.over:
        game.step(agent.choose(game))
        samples.append(board_stats(game.board))
        if on_step is not None:
            on_step(game)

    return GameResult.from_game_stats(
        agent=agent.name,
        seed=game.seed,
        agent_seed=agent_seed,
        score=game.score,
        lines_cleared=game.lines_cleared,
        pieces_placed=game.pieces_placed,
        cause=game.cause,
        final=board_stats(game.board),
        samples=samples,
    )
