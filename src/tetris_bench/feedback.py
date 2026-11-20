"""Turning a finished game into something a model can learn from.

The feedback summary is the improvement loop's only teaching signal, and what it
contains decides what the benchmark measures. It reports **symptoms, not
diagnoses**: the score, the lines, the holes, how tall the stack got, how the
game ended, and a couple of board snapshots. The model has to work out for itself
why those numbers came about.

That is deliberate. We already have tooling that can say "your function scored
every candidate identically" or "your hole count is counting cells near the top
of the board". Putting those conclusions in the prompt would very likely speed
improvement up -- and would make the resulting curve partly a measure of *our*
diagnostic tooling. Keeping feedback to symptoms keeps the curve a measure of the
model.

One exception, and it is a mechanical one rather than strategic: when a function
never separated its candidates, the summary says so. A model told only "you
scored 0" has no way to know whether its strategy was bad or its arithmetic was
inert, and those need completely different fixes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tetris_bench.agents.strategy import StrategyDiagnostics
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.metrics import holes
from tetris_bench.records import GameResult
from tetris_bench.render import render_board

#: How many board snapshots a summary carries. Two is enough to show where the
#: game ended up and where it went wrong, without burying the numbers.
SNAPSHOT_COUNT = 2


class SnapshotCollector:
    """Keeps the most informative boards from a game.

    Used as ``play_game(..., on_step=collector)``. It holds on to the board with
    the most holes -- the moment the stack became unrecoverable -- and the final
    position. Those two answer "what did I do wrong" and "what killed me", which
    are different questions.
    """

    def __init__(self) -> None:
        self.worst_board: Board | None = None
        self.worst_holes = -1
        self.worst_piece = 0

    def __call__(self, game: Game) -> None:
        count = holes(game.board)
        if count > self.worst_holes:
            self.worst_holes = count
            self.worst_board = game.board
            self.worst_piece = game.pieces_placed

    def snapshots(self, final_board: Board) -> list[tuple[str, str]]:
        """Labelled, rendered boards, most instructive first."""
        shots: list[tuple[str, str]] = []
        if self.worst_board is not None and self.worst_board != final_board:
            shots.append(
                (
                    f"after {self.worst_piece} pieces, at the game's worst point "
                    f"({self.worst_holes} holes)",
                    render_board(self.worst_board),
                )
            )
        shots.append(("the final position", render_board(final_board)))
        return shots[-SNAPSHOT_COUNT:]


@dataclass(frozen=True)
class Feedback:
    """Everything a model is told about how its last function played."""

    result: GameResult
    diagnostics: StrategyDiagnostics
    snapshots: list[tuple[str, str]] = field(default_factory=list)
    sandbox_failures: int = 0
    sandbox_errors: list[str] = field(default_factory=list)
    reference_score: int | None = None

    def render(self) -> str:
        """The summary as it appears in the revision prompt."""
        sections = [self._outcome(), self._board_quality(), self._mechanics()]
        sections = [s for s in sections if s]

        for label, board in self.snapshots:
            sections.append(f"{label}:\n\n```\n{board}\n```")

        return "\n\n".join(sections)

    def _outcome(self) -> str:
        result = self.result
        ending = {
            "block_out": "the stack reached the top and a piece had nowhere to go",
            "piece_limit": "it survived the whole piece budget",
        }.get(result.cause or "", "the game did not run")

        lines = [
            "## How your function played",
            "",
            f"- score: **{result.score}**",
            f"- lines cleared: {result.lines_cleared}",
            f"- pieces placed: {result.pieces_placed}",
            f"- how it ended: {ending}",
        ]
        if self.reference_score is not None:
            lines.append(
                f"- for scale, a good scoring function reaches around "
                f"{self.reference_score} on this piece sequence"
            )
        return "\n".join(lines)

    def _board_quality(self) -> str:
        result = self.result
        return "\n".join(
            [
                "## The state of the board",
                "",
                f"- holes at the end: **{result.final_holes}** "
                f"(average through the game: {result.avg_holes:.1f})",
                f"- tallest column at the end: {result.final_max_height} of 20 "
                f"(average: {result.avg_max_height:.1f})",
                f"- surface unevenness at the end: {result.final_bumpiness}",
            ]
        )

    def _mechanics(self) -> str:
        """Only mechanical facts: whether the function ran and whether it chose.

        A model told nothing but "you scored 0" cannot distinguish a bad strategy
        from arithmetic that never varied, and those need different fixes.
        """
        notes: list[str] = []

        if self.diagnostics.is_degenerate:
            notes.append(
                "- **Your function returned the same score for every candidate move.** "
                "The engine had nothing to choose on, so it played the first legal "
                "placement every turn. Check that each term you compute actually "
                "differs between one candidate placement and another."
            )
        elif self.diagnostics.flat_moves:
            notes.append(
                f"- on {self.diagnostics.flat_moves} of "
                f"{self.diagnostics.moves} moves, every candidate scored the same, "
                f"so the choice was arbitrary"
            )

        if self.sandbox_failures:
            notes.append(
                f"- your function raised or timed out on {self.sandbox_failures} "
                f"placement(s); those were treated as unplayable"
            )
            notes.extend(f"  - {error}" for error in self.sandbox_errors[:3])

        if not notes:
            return ""
        return "\n".join(["## Mechanical notes", "", *notes])


def build_feedback(
    result: GameResult,
    diagnostics: StrategyDiagnostics,
    final_board: Board,
    collector: SnapshotCollector | None = None,
    sandbox_failures: int = 0,
    sandbox_errors: list[str] | None = None,
    reference_score: int | None = None,
) -> Feedback:
    """Assemble a feedback summary from a finished game."""
    snapshots = (
        collector.snapshots(final_board)
        if collector is not None
        else [("the final position", render_board(final_board))]
    )
    return Feedback(
        result=result,
        diagnostics=diagnostics,
        snapshots=snapshots,
        sandbox_failures=sandbox_failures,
        sandbox_errors=list(sandbox_errors or []),
        reference_score=reference_score,
    )


@dataclass(frozen=True)
class MultiSeedFeedback:
    """Feedback aggregated over several piece sequences.

    A single sequence is a noisy estimate of a function's quality -- a fixed,
    deterministic function varies 85-348% across seeds it has not seen
    (docs/findings/held-out-seeds.md). Feeding back one game therefore invites a
    model to tune for that sequence, and the project has already seen a
    training-seed number (400) that was a function's luckiest case out of
    twenty-one rather than its typical one.

    Reporting several games makes the signal about the function instead of the
    sequence. The board snapshots come from the worst game, because that is where
    the failure is most legible.
    """

    results: list[GameResult]
    diagnostics: StrategyDiagnostics
    snapshots: list[tuple[str, str]] = field(default_factory=list)
    sandbox_failures: int = 0
    sandbox_errors: list[str] = field(default_factory=list)
    reference_score: int | None = None

    @property
    def worst(self) -> GameResult:
        """The lowest-scoring game, tie-broken by fewest pieces survived."""
        return min(self.results, key=lambda r: (r.score, r.pieces_placed))

    def _mean(self, attribute: str) -> float:
        values = [getattr(r, attribute) for r in self.results]
        return sum(values) / len(values) if values else 0.0

    def render(self) -> str:
        sections = [self._outcome(), self._board_quality(), self._mechanics()]
        sections = [section for section in sections if section]
        for label, board in self.snapshots:
            sections.append(f"{label}:\n\n```\n{board}\n```")
        return "\n\n".join(sections)

    def _outcome(self) -> str:
        lines = [
            "## How your function played",
            "",
            f"It played {len(self.results)} games, each on a different piece sequence.",
            "",
            "| sequence | score | lines | pieces | holes at end | how it ended |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for result in self.results:
            ending = {
                "block_out": "stack reached the top",
                "piece_limit": "survived the budget",
            }.get(result.cause or "", "did not run")
            lines.append(
                f"| {result.seed} | {result.score} | {result.lines_cleared} "
                f"| {result.pieces_placed} | {result.final_holes} | {ending} |"
            )
        lines += [
            "",
            f"- mean score: **{self._mean('score'):.0f}**",
            f"- mean pieces placed: {self._mean('pieces_placed'):.1f}",
            f"- mean holes at the end: {self._mean('final_holes'):.1f}",
        ]
        if self.reference_score is not None:
            lines.append(
                f"- for scale, a good scoring function survives the full piece "
                f"budget and scores around {self.reference_score}"
            )
        return "\n".join(lines)

    def _board_quality(self) -> str:
        worst = self.worst
        return "\n".join(
            [
                f"## The board in your worst game (sequence {worst.seed})",
                "",
                f"- holes at the end: **{worst.final_holes}** "
                f"(average through that game: {worst.avg_holes:.1f})",
                f"- tallest column at the end: {worst.final_max_height} of 20 "
                f"(average: {worst.avg_max_height:.1f})",
                f"- surface unevenness at the end: {worst.final_bumpiness}",
            ]
        )

    def _mechanics(self) -> str:
        """Mechanical facts only, pooled across the games. See Feedback._mechanics."""
        notes: list[str] = []
        if self.diagnostics.is_degenerate:
            notes.append(
                "- **Your function returned the same score for every candidate move,** "
                "or a difference too small to change which move was chosen. The engine "
                "had nothing to choose on, so it played the first legal placement every "
                "turn. Check that each term you compute actually differs between one "
                "candidate placement and another, by enough to matter."
            )
        elif self.diagnostics.flat_moves:
            notes.append(
                f"- on {self.diagnostics.flat_moves} of {self.diagnostics.moves} moves "
                f"every candidate scored the same, so the choice was arbitrary"
            )
        if self.sandbox_failures:
            notes.append(
                f"- your function raised or timed out on {self.sandbox_failures} "
                f"placement(s); those were treated as unplayable"
            )
            notes.extend(f"  - {error}" for error in self.sandbox_errors[:3])
        if not notes:
            return ""
        return "\n".join(["## Mechanical notes", "", *notes])
