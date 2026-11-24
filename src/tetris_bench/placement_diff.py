"""Did a revision change any decision at all?

The 8B loop turned up revisions that rewrite a scoring function and then score
**identically** on every held-out sequence -- one of them provably, because every
weight had been doubled and scaling a linear score uniformly cannot move its
argmax. That test counted exact ties in the final totals, which makes it a
*lower bound* on inertness by construction: a revision that changes one decision
in a thousand, or that changes several and happens to end on the same total,
counts as having changed something.

This module measures the thing the totals were standing in for: **how many
placements the two functions would choose differently, given the same boards.**

The comparison is one-sided on purpose. Two functions playing the same seed
diverge into different games at their first disagreement, after which they are
no longer being asked the same question -- so comparing two independent playouts
measures mostly how far the trajectories drifted apart. Instead the game is
driven by function A and *both* functions are asked about every board A actually
reaches. The reported rate is therefore "how often would B have chosen
otherwise, in the situations A gets into", which is well defined, and the first
divergence is the point past which the games would have differed at all.

Three consequences worth keeping in mind when reading the numbers:

- **0 divergences is strong.** It means B agrees with A on every board of ten
  full games, which for a weighting change is a statement about the whole
  function and not about one lucky total.
- **A non-zero rate is a floor, not the effect size.** One early divergence
  changes every board after it, so a rate of 1% can still mean two completely
  different games.
- **It is not symmetric.** Driving with B would sample different boards and can
  give a different count. The pair is reported A -> B, in iteration order,
  which is the direction the revision was made in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement
from tetris_bench.runner import play_game
from tetris_bench.sandbox import (
    SandboxError,
    SandboxLimits,
    ScoringSandbox,
    build_items,
)


def choose_index(scores: Sequence[float]) -> int:
    """The index a scoring agent would play: the first maximum.

    This duplicates the rule in :meth:`StrategyAgent.choose` rather than sharing
    it, so that adding this analysis cannot change the behaviour of the agent
    every published number was measured with. ``test_placement_diff`` asserts
    the two agree, including on ties and on an all-``-inf`` board.
    """
    return max(range(len(scores)), key=lambda index: scores[index])


@dataclass(frozen=True)
class MoveComparison:
    """What two functions made of one piece's candidate placements."""

    chosen_a: int
    chosen_b: int
    identical_scores: bool

    @property
    def diverged(self) -> bool:
        return self.chosen_a != self.chosen_b


def compare_scores(a: Sequence[float], b: Sequence[float]) -> MoveComparison:
    """Compare two score vectors over the same candidates.

    ``identical_scores`` is the stronger property: equal vectors cannot diverge
    on this board or any other board with the same candidates, whereas equal
    *choices* can come from quite different arithmetic.
    """
    if len(a) != len(b):
        raise ValueError(f"score vectors cover different candidates: {len(a)} vs {len(b)}")
    return MoveComparison(choose_index(a), choose_index(b), list(a) == list(b))


@dataclass
class PairDiff:
    """The result of comparing one revision against the function it revised."""

    label: str
    moves: int = 0
    diverged: int = 0
    identical_score_moves: int = 0
    first_divergence: int | None = None
    games: int = 0
    failure: str | None = None

    @property
    def rate(self) -> float:
        """Share of decisions B would have made differently."""
        return self.diverged / self.moves if self.moves else 0.0

    @property
    def inert(self) -> bool:
        """B never once chose differently, over every board A reached."""
        return self.moves > 0 and self.diverged == 0

    @property
    def arithmetically_identical(self) -> bool:
        """Stronger: B scored every candidate exactly as A did, everywhere."""
        return self.moves > 0 and self.identical_score_moves == self.moves


class ComparingAgent:
    """Plays A's choice on every board, recording where B would have differed.

    An agent rather than a bespoke game loop so that :func:`play_game` stays the
    only place the rules of a game are written down.
    """

    def __init__(self, box_a: ScoringSandbox, box_b: ScoringSandbox) -> None:
        self.name = "placement-diff"
        self.box_a = box_a
        self.box_b = box_b
        self.moves = 0
        self.diverged = 0
        self.identical_score_moves = 0
        self.first_divergence: int | None = None

    def choose(self, game: Game) -> Placement:
        placements = game.legal_placements()
        if not placements:
            raise ValueError("no legal placements: the game is over and should not be stepped")

        # Built once and handed to both workers, so the two functions are
        # answering a byte-identical question and no engine work is repeated.
        items = build_items(game.board, placements)
        comparison = compare_scores(self.box_a.score(items), self.box_b.score(items))

        self.moves += 1
        self.identical_score_moves += comparison.identical_scores
        if comparison.diverged:
            self.diverged += 1
            if self.first_divergence is None:
                self.first_divergence = self.moves
        return placements[comparison.chosen_a]


def diff_pair(
    label: str,
    source_a: str,
    source_b: str,
    seeds: Sequence[int],
    max_pieces: int = 2000,
    limits: SandboxLimits | None = None,
) -> PairDiff:
    """Play ``source_a`` on every seed, asking ``source_b`` about each board.

    Any sandbox failure -- a rejection at validation, a crash, or the whole-game
    deadline -- is recorded on the result and the remaining seeds are skipped,
    rather than raised: one unplayable pair must not end a sweep over a hundred
    of them.
    """
    diff = PairDiff(label=label)
    try:
        with (
            ScoringSandbox(source_a, limits=limits or SandboxLimits()) as box_a,
            ScoringSandbox(source_b, limits=limits or SandboxLimits()) as box_b,
        ):
            agent = ComparingAgent(box_a, box_b)
            for seed in seeds:
                play_game(Game(seed=seed, max_pieces=max_pieces), agent)
                diff.games += 1
            diff.moves = agent.moves
            diff.diverged = agent.diverged
            diff.identical_score_moves = agent.identical_score_moves
            diff.first_divergence = agent.first_divergence
    except SandboxError as error:
        diff.failure = str(error)
    return diff


@dataclass(frozen=True)
class Pairing:
    """One revision: the function handed to the model, and what came back."""

    model: str
    chain: int
    iteration_a: int
    iteration_b: int

    @property
    def label(self) -> str:
        return f"{self.model}-chain{self.chain}-iter{self.iteration_a}->{self.iteration_b}"

    @property
    def name_a(self) -> str:
        return f"{self.model}-chain{self.chain}-iter{self.iteration_a}"

    @property
    def name_b(self) -> str:
        return f"{self.model}-chain{self.chain}-iter{self.iteration_b}"

    @property
    def skipped_rejection(self) -> bool:
        """A rejected generation sits between these two iterations."""
        return self.iteration_b != self.iteration_a + 1


def lineage_pairs(rows: Sequence[dict]) -> list[Pairing]:
    """Every revision in a loop log, as the model actually received it.

    Each played position is paired with the **previous played** position in its
    chain, not with ``iteration - 1``, because that is what the loop hands over:
    a rejected generation never becomes the next prompt's "your previous
    function", so the revision the model made skips it. Where nothing was
    rejected the two readings coincide, and :attr:`Pairing.skipped_rejection`
    marks the cases where they do not.
    """
    played: dict[tuple[str, int], list[int]] = {}
    for row in rows:
        if not row.get("played"):
            continue
        played.setdefault((row["model"], row["chain"]), []).append(row["iteration"])

    pairs: list[Pairing] = []
    for (model, chain), iterations in sorted(played.items()):
        ordered = sorted(set(iterations))
        for before, after in zip(ordered, ordered[1:], strict=False):
            pairs.append(Pairing(model=model, chain=chain, iteration_a=before, iteration_b=after))
    return pairs
