"""Seeded 7-bag piece generation.

A 7-bag randomiser shuffles all seven tetrominoes and deals them out one by one,
then shuffles a fresh set. That bounds how long you can wait for any given piece
and is what modern Tetris games use, so a benchmark built on it rewards real
stacking skill rather than luck.

Everything here is driven by a single seed, which is what makes runs comparable:
every model faces the identical piece sequence for a given seed.
"""

from __future__ import annotations

import random
from collections import deque

from tetris_bench.engine.pieces import PIECE_KINDS


class SevenBag:
    """A deterministic piece queue you can also look ahead into.

    The queue is topped up lazily, one bag at a time, so asking to preview more
    pieces never changes the sequence that comes out of :meth:`draw`.
    """

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._queue: deque[str] = deque()

    def _refill(self) -> None:
        """Shuffle a fresh set of all seven pieces onto the back of the queue."""
        bag = list(PIECE_KINDS)
        self._rng.shuffle(bag)
        self._queue.extend(bag)

    def _ensure(self, count: int) -> None:
        """Make sure at least ``count`` pieces are queued up."""
        while len(self._queue) < count:
            self._refill()

    def draw(self) -> str:
        """Take the next piece out of the queue."""
        self._ensure(1)
        return self._queue.popleft()

    def peek(self, count: int) -> tuple[str, ...]:
        """Look at the next ``count`` pieces without consuming them."""
        if count < 0:
            raise ValueError(f"cannot peek a negative number of pieces: {count}")
        self._ensure(count)
        return tuple(self._queue[i] for i in range(count))
