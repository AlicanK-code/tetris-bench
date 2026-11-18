"""Tests for legal-placement enumeration."""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.engine.pieces import PIECE_KINDS, PIECES
from tetris_bench.engine.placements import legal_placements


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("O", 9), ("I", 17), ("S", 17), ("Z", 17), ("T", 34), ("J", 34), ("L", 34)],
)
def test_placement_counts_on_an_empty_board(kind, expected):
    """Each rotation contributes (board width - piece width + 1) columns."""
    assert len(legal_placements(Board.empty(10, 20), kind)) == expected


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_placements_are_unique(kind):
    """Deduplicating rotations means a model is never offered the same move twice."""
    placements = legal_placements(Board.empty(10, 20), kind)
    assert len({p.cells for p in placements}) == len(placements)


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_every_placement_lands_inside_the_board(kind):
    board = Board.empty(10, 20)
    for placement in legal_placements(board, kind):
        for row, col in placement.cells:
            assert 0 <= row < board.height
            assert 0 <= col < board.width


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_every_placement_rests_on_the_floor_of_an_empty_board(kind):
    """With nothing to land on, a dropped piece must touch the bottom row."""
    board = Board.empty(10, 20)
    for placement in legal_placements(board, kind):
        assert placement.landing_row == board.height - 1


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_no_placement_overlaps_existing_blocks(kind):
    board = Board.from_strings(
        [
            "..........",
            "..........",
            "..........",
            "...XX.....",
            "XXXXX..XXX",
        ]
    )
    for placement in legal_placements(board, kind):
        for row, col in placement.cells:
            assert not board.is_filled(row, col)


def test_piece_lands_on_top_of_the_stack():
    board = Board.from_strings(
        [
            "....",
            "....",
            "X...",
            "X...",
        ]
    )
    # The flat O piece over columns 0-1 has to sit on the two-high tower.
    placements = legal_placements(board, "O")
    over_left = next(p for p in placements if p.column == 0)
    assert over_left.cells == ((0, 0), (0, 1), (1, 0), (1, 1))


def test_vertical_i_drops_into_a_deep_well():
    board = Board.from_strings(
        [
            ".XXXXXXXXX",
            ".XXXXXXXXX",
            ".XXXXXXXXX",
            ".XXXXXXXXX",
        ]
    )
    placements = legal_placements(board, "I")
    assert len(placements) == 1
    assert placements[0].cells == ((0, 0), (1, 0), (2, 0), (3, 0))


def test_full_board_has_no_placements():
    """An empty placement list is exactly how the engine detects game over."""
    board = Board.from_strings(["XXXX"] * 4)
    for kind in PIECE_KINDS:
        assert legal_placements(board, kind) == []


def test_piece_that_would_rest_above_the_ceiling_is_illegal():
    """A 3-high board cannot hold an upright I piece, so those columns drop out."""
    board = Board.empty(10, 3)
    upright = [p for p in legal_placements(board, "I") if PIECES["I"].height(p.rotation) == 4]
    assert upright == []
    # The flat rotation still fits.
    assert len(legal_placements(board, "I")) == 7


def test_placement_records_its_rotation_and_column():
    board = Board.empty(10, 20)
    for placement in legal_placements(board, "T"):
        piece = PIECES["T"]
        span = piece.width(placement.rotation)
        assert 0 <= placement.column <= board.width - span
        assert placement.cells[0][1] >= placement.column


def test_placements_are_frozen_and_hashable():
    placement = legal_placements(Board.empty(10, 20), "O")[0]
    assert hash(placement) is not None
    with pytest.raises(AttributeError):
        placement.column = 5
