"""Tests for the game session: scoring, line clears and game over."""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.engine.pieces import PIECES
from tetris_bench.engine.placements import Placement, legal_placements

EMPTY_ROW = "." * 10
ALMOST_FULL_ROW = "." + "X" * 9


def lowest_first(game: Game) -> Placement:
    """A throwaway policy: drop the piece as deep as possible, leftmost wins ties.

    Not a good Tetris player -- it happily buries holes -- but it is deterministic,
    which is what these tests need.
    """
    return max(game.legal_placements(), key=lambda p: (p.landing_row, -p.column))


def upright_i_in_column_zero(game: Game) -> Placement:
    """The vertical I placement in the leftmost column."""
    return next(
        p for p in game.legal_placements() if p.column == 0 and PIECES["I"].height(p.rotation) == 4
    )


class TestNewGame:
    def test_starts_in_play(self):
        game = Game(seed=1)
        assert not game.over
        assert game.cause is None
        assert game.score == 0
        assert game.lines_cleared == 0
        assert game.pieces_placed == 0

    def test_starts_with_an_empty_board(self):
        assert Game(seed=1).board == Board.empty(10, 20)

    def test_has_a_current_piece_and_a_preview(self):
        game = Game(seed=1, preview=5)
        assert game.current in PIECES
        assert len(game.next_pieces) == 5

    def test_preview_does_not_include_the_current_piece(self):
        """The current piece has already been drawn out of the bag."""
        game = Game(seed=1)
        first_next = game.next_pieces[0]
        game.step(lowest_first(game))
        assert game.current == first_next

    def test_same_seed_gives_the_same_opening_pieces(self):
        assert Game(seed=99).next_pieces == Game(seed=99).next_pieces

    @pytest.mark.parametrize("max_pieces", [0, -1, -500])
    def test_rejects_a_meaningless_piece_budget(self, max_pieces):
        """A cap below 1 has no sensible reading, so it is refused outright.

        Defining a behaviour for it instead would turn a config typo into a
        silently short run rather than an error at the point of the mistake.
        """
        with pytest.raises(ValueError, match="max_pieces must be at least 1"):
            Game(seed=1, max_pieces=max_pieces)

    def test_accepts_a_budget_of_one(self):
        game = Game(seed=1, max_pieces=1)
        assert not game.over
        game.step(lowest_first(game))
        assert game.over
        assert game.cause == "piece_limit"
        assert game.pieces_placed == 1

    def test_accepts_no_limit(self):
        assert Game(seed=1, max_pieces=None).max_pieces is None


class TestStep:
    def test_locks_the_piece_onto_the_board(self):
        game = Game(seed=1)
        game.step(lowest_first(game))
        filled = sum(cell for row in game.board.occupancy() for cell in row)
        assert filled == 4
        assert game.pieces_placed == 1

    def test_returns_the_number_of_lines_cleared(self):
        game = Game(seed=1)
        assert game.step(lowest_first(game)) == 0

    def test_rejects_a_placement_for_the_wrong_piece(self):
        game = Game(seed=1)
        wrong = next(k for k in PIECES if k != game.current)
        placement = legal_placements(game.board, wrong)[0]
        with pytest.raises(ValueError, match="current piece is"):
            game.step(placement)

    def test_rejects_a_placement_that_is_not_legal(self):
        game = Game(seed=1)
        floating = Placement(
            kind=game.current,
            rotation=0,
            column=0,
            row=0,
            cells=((0, 0), (0, 1), (0, 2), (0, 3)),
        )
        with pytest.raises(ValueError, match="illegal placement"):
            game.step(floating)

    def test_rejects_stepping_a_finished_game(self):
        game = Game(seed=1, max_pieces=1)
        game.step(lowest_first(game))
        assert game.over
        with pytest.raises(RuntimeError, match="already over"):
            game.step(lowest_first(game))


class TestScoring:
    def test_single_line_scores_100(self):
        game = Game(seed=1)
        game.board = Board.from_strings([EMPTY_ROW] * 19 + [ALMOST_FULL_ROW])
        game.current = "I"
        assert game.step(upright_i_in_column_zero(game)) == 1
        assert game.score == 100
        assert game.lines_cleared == 1

    def test_tetris_scores_800(self):
        game = Game(seed=1)
        game.board = Board.from_strings([EMPTY_ROW] * 16 + [ALMOST_FULL_ROW] * 4)
        game.current = "I"
        assert game.step(upright_i_in_column_zero(game)) == 4
        assert game.score == 800
        assert game.lines_cleared == 4

    def test_a_tetris_beats_four_singles(self):
        """The steep curve is what rewards learning to build for big clears."""
        from tetris_bench.engine.game import LINE_SCORES

        assert LINE_SCORES[4] > 4 * LINE_SCORES[1]

    def test_clearing_empties_the_board_again(self):
        game = Game(seed=1)
        game.board = Board.from_strings([EMPTY_ROW] * 16 + [ALMOST_FULL_ROW] * 4)
        game.current = "I"
        game.step(upright_i_in_column_zero(game))
        assert game.board == Board.empty(10, 20)

    def test_score_accumulates_across_placements(self):
        game = Game(seed=1)
        game.board = Board.from_strings([EMPTY_ROW] * 19 + [ALMOST_FULL_ROW])
        game.current = "I"
        game.step(upright_i_in_column_zero(game))
        game.board = Board.from_strings([EMPTY_ROW] * 19 + [ALMOST_FULL_ROW])
        game.current = "I"
        game.step(upright_i_in_column_zero(game))
        assert game.score == 200
        assert game.lines_cleared == 2


class TestGameOver:
    def test_piece_limit_ends_the_game(self):
        game = Game(seed=1, max_pieces=3)
        for _ in range(3):
            assert not game.over
            game.step(lowest_first(game))
        assert game.over
        assert game.cause == "piece_limit"
        assert game.pieces_placed == 3

    def test_block_out_is_simply_having_no_legal_placements(self):
        game = Game(seed=1)
        game.board = Board.from_strings([EMPTY_ROW] + ["X" * 10] * 19)
        game.current = "O"  # two rows tall, and only one free row remains
        assert game.legal_placements() == []

    def test_a_bad_policy_eventually_blocks_out(self):
        """On a narrow board, stacking without clearing runs out of room."""
        game = Game(seed=4, width=5, height=8, max_pieces=None)
        for _ in range(1000):
            if game.over:
                break
            game.step(game.legal_placements()[0])
        assert game.over
        assert game.cause == "block_out"
        assert game.pieces_placed > 0


class TestDeterminism:
    def test_identical_seeds_and_policy_give_identical_games(self):
        """Reproducibility from seed alone -- the basis of comparing models."""

        def play(seed: int) -> tuple[int, int, int, str]:
            game = Game(seed=seed, max_pieces=60)
            while not game.over:
                game.step(lowest_first(game))
            return game.score, game.lines_cleared, game.pieces_placed, str(game.board)

        assert play(17) == play(17)

    def test_different_seeds_give_different_games(self):
        def board_after(seed: int) -> str:
            game = Game(seed=seed, max_pieces=40)
            while not game.over:
                game.step(lowest_first(game))
            return str(game.board)

        assert board_after(1) != board_after(2)

    @pytest.mark.parametrize("seed", [1, 2, 17, 123])
    def test_a_full_game_runs_to_completion_without_errors(self, seed):
        """The engine must always terminate with a recorded reason.

        `lowest_first` buries holes, so it typically blocks out well before the
        piece budget. The point here is that a long game never crashes and never
        ends in an undefined state, not that any particular policy survives.
        """
        game = Game(seed=seed, max_pieces=200)
        while not game.over:
            game.step(lowest_first(game))
        assert game.cause in {"block_out", "piece_limit"}
        assert 0 < game.pieces_placed <= 200
        assert game.score >= 0

    def test_a_greedy_policy_blocks_out_before_the_piece_budget(self):
        """Documents the baseline Milestone 2's heuristic agent has to beat."""
        game = Game(seed=17, max_pieces=200)
        while not game.over:
            game.step(lowest_first(game))
        assert game.cause == "block_out"
        assert game.pieces_placed < 200
