"""A uniformly random agent, used as the floor to measure everything against."""

from __future__ import annotations

import random

from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement


class RandomAgent:
    """Picks uniformly at random among the legal placements.

    The agent owns its own :class:`random.Random` instance, and that detail
    matters more than the rest of this file:

    - Using the module-level ``random.choice`` would draw from one stream shared
      by the whole process, so a "seeded" run would change whenever anything else
      touched :mod:`random` -- test ordering alone could move the numbers.
    - Reusing the game's own piece RNG would be worse. The agent's draws would
      shift the piece sequence, so two agents would face *different pieces* and
      the premise that every model plays identical seeds would silently fail.

    So a run is identified by two independent seeds: one for the pieces, one for
    the agent.
    """

    def __init__(self, seed: int) -> None:
        self.name = "random"
        self.seed = seed
        self._rng = random.Random(seed)

    def choose(self, game: Game) -> Placement:
        return self._rng.choice(game.legal_placements())
