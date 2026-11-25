"""The reference players, and the conditions they were measured under.

A rate quoted without its conditions invites exactly one question, and this
project invited it: the README said the hand-written heuristic scores **43.2**
points per piece while the results compared a model against **43.5**. Both
figures were right and neither was labelled, so a reader comparing 50.19 against
43.5 could reasonably ask why the table said 43.2.

The rate is stable, which is the whole reason the project moved its headline to
it -- but "stable" means within about 0.2, not identical:

| condition | heuristic |
|---|---:|
| seeds 1000-1009, 2,000-piece budget | **43.34** |
| seeds 1000-1019, 2,000-piece budget | 43.16 |
| seeds 1000-1019, run to exhaustion (50,000) | 43.46 |

**The first row is canonical**, because it is the condition every model figure in
this project is measured under: the ten held-out sequences the loop evaluates
on, at the default piece budget. Anything compared against a model result uses
:data:`HEURISTIC_RATE`. The other two rows are kept because older write-ups
quote them, and a number that moves when nobody changed anything is worth being
able to explain.

Re-measure with ``uv run python analysis/baselines.py``, which prints all three
rows. It takes about twenty seconds, which is why these are constants here
rather than a fixture in the test suite.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The held-out sequences every curve in this project is read from.
EVAL_SEEDS: tuple[int, ...] = tuple(range(1000, 1010))

#: The default piece budget. A game that reaches it is cut off rather than lost,
#: which censors a *total* and is why the headline is a rate.
MAX_PIECES: int = 2000

#: Points per piece for the hand-written 1-ply heuristic (Lee's 2013 weights) on
#: :data:`EVAL_SEEDS` at :data:`MAX_PIECES`: 84,720 points over 1,955 pieces per
#: game, censored in 8 of 10 games. **This is the number to compare a model
#: against.**
HEURISTIC_RATE: float = 43.34

#: Points per piece for uniform random play under the same conditions, pooled
#: over 20 agent seeds (1,700 points over 5,089 pieces). A single run of random
#: play varies from 0.00 to 1.16, which is why this is pooled and why
#: :data:`tetris_bench.zeros_rate.RANDOM_CEILING` exists as a separate figure.
RANDOM_RATE: float = 0.33


@dataclass(frozen=True)
class Baseline:
    """One reference player under one set of conditions."""

    name: str
    rate: float
    seeds: tuple[int, ...]
    max_pieces: int

    @property
    def conditions(self) -> str:
        """The label that should appear beside the number, every time."""
        return f"seeds {self.seeds[0]}-{self.seeds[-1]}, {self.max_pieces:,}-piece budget"


HEURISTIC = Baseline("hand-written heuristic", HEURISTIC_RATE, EVAL_SEEDS, MAX_PIECES)
RANDOM = Baseline("random", RANDOM_RATE, EVAL_SEEDS, MAX_PIECES)


def measure_heuristic(
    seeds: tuple[int, ...] = EVAL_SEEDS, max_pieces: int = MAX_PIECES
) -> tuple[float, int, int, int]:
    """Replay the heuristic and return (rate, total score, total pieces, censored).

    Imported lazily so that reading a constant from this module does not drag in
    the engine and the agents.
    """
    from tetris_bench.agents.heuristic import heuristic_agent
    from tetris_bench.engine.game import Game
    from tetris_bench.runner import play_game

    agent = heuristic_agent()
    score = pieces = censored = 0
    for seed in seeds:
        result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
        score += result.score
        pieces += result.pieces_placed
        censored += result.pieces_placed >= max_pieces
    return (score / pieces if pieces else 0.0), score, pieces, censored


def measure_random(
    seeds: tuple[int, ...] = EVAL_SEEDS,
    max_pieces: int = MAX_PIECES,
    agent_seeds: int = 20,
) -> tuple[float, int, int]:
    """Pooled random rate: (rate, total score, total pieces).

    Pooled rather than averaged over per-run rates, for the same reason every
    other rate here is totals over totals: a 26-piece game must not weigh as
    much as a 2,000-piece one.
    """
    from tetris_bench.agents.random_agent import RandomAgent
    from tetris_bench.engine.game import Game
    from tetris_bench.runner import play_game

    score = pieces = 0
    for agent_seed in range(agent_seeds):
        agent = RandomAgent(seed=agent_seed)
        for seed in seeds:
            result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
            score += result.score
            pieces += result.pieces_placed
    return (score / pieces if pieces else 0.0), score, pieces
