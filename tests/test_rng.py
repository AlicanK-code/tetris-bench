"""Tests for the seeded 7-bag piece generator."""

import pytest

from tetris_bench.engine.pieces import PIECE_KINDS
from tetris_bench.engine.rng import SevenBag


def test_same_seed_gives_the_same_sequence():
    """This is the property the whole benchmark rests on."""
    a = [SevenBag(seed=42).draw() for _ in range(1)]
    first = SevenBag(seed=42)
    second = SevenBag(seed=42)
    assert [first.draw() for _ in range(50)] == [second.draw() for _ in range(50)]
    assert a  # first draw is reproducible too


def test_different_seeds_give_different_sequences():
    first = [SevenBag(seed=1).draw() for _ in range(20)]
    second = [SevenBag(seed=2).draw() for _ in range(20)]
    assert first != second


@pytest.mark.parametrize("seed", range(5))
def test_every_group_of_seven_is_a_permutation(seed):
    """The point of a 7-bag: you never wait more than 12 pieces for an I."""
    bag = SevenBag(seed=seed)
    for _ in range(10):
        drawn = [bag.draw() for _ in range(7)]
        assert sorted(drawn) == sorted(PIECE_KINDS)


def test_peek_does_not_consume():
    bag = SevenBag(seed=7)
    preview = bag.peek(5)
    assert bag.peek(5) == preview
    assert [bag.draw() for _ in range(5)] == list(preview)


def test_peek_beyond_one_bag_still_matches_the_draw_order():
    """Looking far ahead must not disturb the sequence."""
    peeking = SevenBag(seed=3)
    drawing = SevenBag(seed=3)
    preview = peeking.peek(30)
    assert [drawing.draw() for _ in range(30)] == list(preview)


def test_peek_zero_is_empty():
    assert SevenBag(seed=1).peek(0) == ()


def test_peek_rejects_negative_counts():
    with pytest.raises(ValueError, match="negative"):
        SevenBag(seed=1).peek(-1)


def test_draw_after_peek_is_unaffected_by_how_much_was_peeked():
    shallow = SevenBag(seed=11)
    deep = SevenBag(seed=11)
    shallow.peek(1)
    deep.peek(100)
    assert [shallow.draw() for _ in range(20)] == [deep.draw() for _ in range(20)]
