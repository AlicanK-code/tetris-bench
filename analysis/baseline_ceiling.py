"""Reference numbers for the two hand-written agents, reported honestly.

Every model result in this project is quoted against a baseline, so the baseline
had better mean something. It turns out the obvious way to quote it does not.

**Score is a censored measure.** A game stops at the piece budget, so an agent
that survives the budget does not report how good it is -- it reports how long
it was allowed to play. The heuristic baseline is the extreme case: it survives
20,000 pieces for 876,000 points with no sign of dying, so there is no cap at
which it yields a finite ceiling. "The heuristic scores 21,600" is really "the
heuristic scores 21,600 *per 500 pieces*", and raising the budget raises the
number without the agent having changed at all.

So this script reports two separable things, and refuses to collapse them:

*Survival* -- does the agent die, and after how many pieces? This is where the
hand-written heuristic and a model-written function differ most.

*Rate* -- points and lines per piece *while alive*. This is comparable across
agents regardless of budget, and it is the only figure that survives a change
of cap.

Keeping them apart matters for the headline. Measured at the time of writing,
the best function the loop has produced scores 40.2 points per piece against
the heuristic's 43.5 -- about 92% of the rate -- while dying after 626 pieces
where the heuristic is effectively immortal. Quoting totals alone would have
called that "69% of the heuristic" and buried the actual finding, which is that
the model matched the heuristic's scoring efficiency and failed entirely at
staying alive.

    uv run python analysis/baseline_ceiling.py
    uv run python analysis/baseline_ceiling.py --max-pieces 20000 --seeds 5
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from tetris_bench.agents.heuristic import heuristic_agent
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.engine.game import DEFAULT_MAX_PIECES, Game
from tetris_bench.runner import play_game

#: The held-out sequences the improvement curve is read from, so baselines are
#: quoted on exactly the seeds the models are quoted on.
HELD_OUT_SEEDS = tuple(range(1000, 1020))


@dataclass(frozen=True)
class Reference:
    """One agent's numbers across a seed set, with censoring made explicit."""

    agent: str
    max_pieces: int
    scores: tuple[int, ...]
    lines: tuple[int, ...]
    pieces: tuple[int, ...]
    censored: int

    @property
    def mean_score(self) -> float:
        return statistics.fmean(self.scores)

    @property
    def mean_pieces(self) -> float:
        return statistics.fmean(self.pieces)

    @property
    def points_per_piece(self) -> float:
        """Rate while alive -- the figure that does not move when the cap does."""
        total_pieces = sum(self.pieces)
        return sum(self.scores) / total_pieces if total_pieces else 0.0

    @property
    def lines_per_piece(self) -> float:
        total_pieces = sum(self.pieces)
        return sum(self.lines) / total_pieces if total_pieces else 0.0

    @property
    def score_spread(self) -> float:
        """Standard deviation of the total.

        Worth printing next to the censoring count, because a censored agent
        looks *more* reliable than it is: the cap truncates exactly the games
        that would have run long, so it removes the variance it is hiding.
        """
        return statistics.stdev(self.scores) if len(self.scores) > 1 else 0.0


def measure(agent_kind: str, seeds: tuple[int, ...], max_pieces: int) -> Reference:
    """Play one reference agent across every seed."""
    scores: list[int] = []
    lines: list[int] = []
    pieces: list[int] = []
    censored = 0

    for seed in seeds:
        # A fresh agent per game: the random one carries RNG state, and reusing
        # it would make seed N's game depend on seed N-1's.
        agent = heuristic_agent() if agent_kind == "heuristic" else RandomAgent(seed=0)
        result = play_game(Game(seed=seed, max_pieces=max_pieces), agent)
        scores.append(result.score)
        lines.append(result.lines_cleared)
        pieces.append(result.pieces_placed)
        if result.cause == "piece_limit":
            censored += 1

    return Reference(
        agent=agent_kind,
        max_pieces=max_pieces,
        scores=tuple(scores),
        lines=tuple(lines),
        pieces=tuple(pieces),
        censored=censored,
    )


def report(refs: list[Reference], seeds: tuple[int, ...]) -> None:
    cap = refs[0].max_pieces
    print(f"Reference agents, {len(seeds)} held-out seeds, {cap}-piece budget")
    print("=" * 78)
    header = (
        f"{'agent':<12}{'mean score':>13}{'+/- sd':>10}{'pieces':>9}"
        f"{'pts/pc':>9}{'lines/pc':>10}{'capped':>9}"
    )
    print(header)
    print("-" * 78)
    for ref in refs:
        print(
            f"{ref.agent:<12}{ref.mean_score:>13,.0f}{ref.score_spread:>10,.0f}"
            f"{ref.mean_pieces:>9,.0f}{ref.points_per_piece:>9.1f}"
            f"{ref.lines_per_piece:>10.2f}{ref.censored:>6}/{len(seeds)}"
        )
    print()

    for ref in refs:
        if ref.censored == len(seeds):
            print(
                f"  {ref.agent}: survived every game. Its mean score is "
                f"{ref.mean_pieces:,.0f} pieces x {ref.points_per_piece:.1f} "
                f"points/piece -- a measure of the budget, NOT a ceiling. "
                f"Quote the rate."
            )
        elif ref.censored:
            print(
                f"  {ref.agent}: censored on {ref.censored} of {len(seeds)} games, "
                f"so its mean score is a lower bound. Raise --max-pieces or "
                f"quote the rate."
            )
        else:
            print(f"  {ref.agent}: died in every game, so its mean score is a real measure.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pieces", type=int, default=DEFAULT_MAX_PIECES)
    parser.add_argument(
        "--seeds",
        type=int,
        default=len(HELD_OUT_SEEDS),
        help=f"how many held-out seeds to use (max {len(HELD_OUT_SEEDS)})",
    )
    args = parser.parse_args()

    seeds = HELD_OUT_SEEDS[: args.seeds]
    refs = [measure(kind, seeds, args.max_pieces) for kind in ("random", "heuristic")]
    report(refs, seeds)


if __name__ == "__main__":
    main()
