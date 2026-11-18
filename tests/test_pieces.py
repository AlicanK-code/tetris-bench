"""Tests for tetromino shapes and rotation generation."""

import pytest

from tetris_bench.engine.pieces import (
    PIECE_KINDS,
    PIECES,
    SPAWN_SHAPES,
    normalise,
    rotate_cw,
)


def test_all_seven_pieces_exist():
    assert set(PIECES) == set(PIECE_KINDS)
    assert len(PIECE_KINDS) == 7


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_every_rotation_has_four_cells(kind):
    for shape in PIECES[kind].rotations:
        assert len(shape) == 4, f"{kind} has a rotation with {len(shape)} cells"
        assert len(set(shape)) == 4, f"{kind} has a rotation with duplicate cells"


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_every_rotation_is_normalised(kind):
    """Normalisation is what lets placements enumerate columns from 0."""
    for shape in PIECES[kind].rotations:
        assert min(r for r, _ in shape) == 0
        assert min(c for _, c in shape) == 0


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("O", 1), ("I", 2), ("S", 2), ("Z", 2), ("T", 4), ("J", 4), ("L", 4)],
)
def test_distinct_rotation_counts(kind, expected):
    """Duplicate orientations are dropped, so O has one state and I/S/Z have two."""
    assert PIECES[kind].rotation_count == expected


@pytest.mark.parametrize("kind", PIECE_KINDS)
def test_four_clockwise_turns_return_to_start(kind):
    shape = normalise(SPAWN_SHAPES[kind])
    turned = shape
    for _ in range(4):
        turned = rotate_cw(turned)
    assert turned == shape


def test_normalise_shifts_to_origin_and_sorts():
    assert normalise(((5, 7), (5, 8), (6, 7), (6, 8))) == ((0, 0), (0, 1), (1, 0), (1, 1))


def test_rotate_cw_turns_i_piece_upright():
    horizontal = normalise(SPAWN_SHAPES["I"])
    assert horizontal == ((0, 0), (0, 1), (0, 2), (0, 3))
    assert rotate_cw(horizontal) == ((0, 0), (1, 0), (2, 0), (3, 0))


def test_o_piece_is_unchanged_by_rotation():
    square = normalise(SPAWN_SHAPES["O"])
    assert rotate_cw(square) == square


@pytest.mark.parametrize(
    ("kind", "rotation", "width", "height"),
    [
        ("I", 0, 4, 1),
        ("I", 1, 1, 4),
        ("O", 0, 2, 2),
        ("T", 0, 3, 2),
        ("T", 1, 2, 3),
    ],
)
def test_width_and_height(kind, rotation, width, height):
    piece = PIECES[kind]
    assert piece.width(rotation) == width
    assert piece.height(rotation) == height
