"""The direct agent: one model call per piece, choosing from the legal moves.

This is milestone 7, and it exists as a **baseline for comparison** rather than
as a serious contender. The prior work already reports that picking moves
directly fails where writing a scoring function succeeds, and the arithmetic of
running it says why it cannot be the main mode: ``strategy`` mode calls a model
once per *game*, while this calls it once per *piece*. A 2,000-piece game is
2,000 calls, which at the local rungs' latencies is hours for one game that
``strategy`` plays in under a second.

So the value here is a demonstration, and the figure to read off it is the cost
ratio -- tokens and seconds per piece against the same model in ``strategy``
mode -- not the score.

Three choices are made here explicitly.

**The answer is an index, not a move.** :func:`~tetris_bench.render.render_placements`
numbers the legal placements and the model replies with one number. Every index
on offer is legal by construction, so the model cannot propose an illegal move
and nothing is spent on validating geometry. That is deliberately generous: it
isolates *can you choose well* from *can you emit a well-formed move*, and the
first is the interesting question. It also means a poor score here cannot be
explained away as a formatting problem.

**A malformed answer costs the turn, and is not rescued.** An unparseable or
out-of-range reply is recorded in ``invalid_outputs`` and the agent plays index
0. Index 0 is arbitrary but deterministic -- the same tie-break
:class:`~tetris_bench.agents.base.ScoringAgent` uses. Falling back to something
*good*, such as the hand-written heuristic, would let a model that never emits a
valid answer score like a competent player, which would hide the failure this
baseline exists to show. An out-of-range index is also never clamped into range,
for the same reason: clamping converts a wrong answer into a legal move.

**Each turn is a fresh, stateless prompt.** No conversation history, no previous
boards. Two reasons: the tokens-in figure per piece stays flat instead of growing
with the game, which is what makes the cost ratio meaningful; and a 2,000-turn
conversation would exceed any local context window long before the game ended.
The board itself carries all the state the choice needs.
"""

from __future__ import annotations

import re

from tetris_bench import prompts
from tetris_bench.clients.client import ModelClient
from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement
from tetris_bench.render import render_placements, render_state

PROMPT_NAME = "direct_v1"
"""The versioned template this agent sends. See :mod:`tetris_bench.prompts`."""

_INTEGER = re.compile(r"\d+")


def parse_index(text: str, count: int) -> int | None:
    """Read the chosen placement index out of a model's reply.

    Returns ``None`` when the reply holds no number, or a number that is not a
    valid index into ``count`` placements. ``None`` means "invalid output", which
    the caller records and recovers from; it never means "pick something near
    enough".

    **The last integer in the text wins.** A model that was asked for a bare
    number and reasoned anyway tends to put its conclusion last ("...so I will
    play 12"), and taking the last number reads that correctly while still
    accepting the well-formed bare ``12``. Taking the first would read the first
    number it happened to mention, which on a reply that restates the options is
    usually not the answer.
    """
    matches = _INTEGER.findall(text)
    if not matches:
        return None
    index = int(matches[-1])
    return index if 0 <= index < count else None


class DirectAgent:
    """Asks a model which legal placement to play, once per piece."""

    def __init__(
        self,
        client: ModelClient,
        *,
        prompt_name: str = PROMPT_NAME,
        show_pieces: bool = False,
        seed: int | None = None,
    ) -> None:
        self._client = client
        self._prompt_name = prompt_name
        self._show_pieces = show_pieces
        self._seed = seed
        self.name = "direct"
        #: Replies that held no usable index. One per piece at worst.
        self.invalid_outputs = 0
        #: The first few bad replies, trimmed, for the CLI to print. Bounded so
        #: a game that fails on every turn cannot grow this without limit.
        self.invalid_samples: list[str] = []

    def build_prompt(self, game: Game, placements: list[Placement]) -> str:
        """Render this turn's prompt.

        Public because the null arm and any cost estimate want the prompt
        without spending a call on it.
        """
        board = game.board
        return prompts.render(
            self._prompt_name,
            state=render_state(game, show_pieces=self._show_pieces),
            placements=render_placements(placements),
            width=board.width,
            height=board.height,
            last_row=board.height - 1,
            last_index=len(placements) - 1,
        )

    def choose(self, game: Game) -> Placement:
        placements = game.legal_placements()
        if not placements:
            raise ValueError("no legal placements: the game is over and should not be stepped")

        prompt = self.build_prompt(game, placements)
        response = self._client.complete([{"role": "user", "content": prompt}], seed=self._seed)
        index = parse_index(response.text, len(placements))

        if index is None:
            self.invalid_outputs += 1
            if len(self.invalid_samples) < 3:
                reply = " ".join(response.text.split())
                self.invalid_samples.append(reply[:120] if reply else "(empty reply)")
            index = 0

        return placements[index]
