"""The strategy agent: play using a scoring function a model wrote.

This is the benchmark's main mode. A model is asked once, before the game, to
write ``score(board, placement) -> float``. The engine then evaluates every legal
placement with it and plays the best one, so the model is not consulted again
during the game. That is what makes the mode cheap enough to run many times, and
what makes the *function* -- rather than any individual move -- the thing being
measured.

The agent is a :class:`~tetris_bench.agents.base.ScoringAgent` in all but name:
it applies a scoring function to every candidate and takes the maximum. The
difference is only where the function came from and that it runs inside
:class:`~tetris_bench.sandbox.ScoringSandbox` rather than in this process.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tetris_bench.clients.client import ChatResponse, ModelClient
from tetris_bench.engine.board import DEFAULT_HEIGHT, DEFAULT_WIDTH
from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement
from tetris_bench.prompts import render
from tetris_bench.sandbox import UNPLAYABLE, ScoringSandbox, build_items

DEFAULT_TEMPLATE = "strategy_v3"
"""The template both callers use, so a one-shot run *is* the loop's iteration 0.

This was `strategy_v2` while the loop used `strategy_v3`, which meant
`tetris-bench strategy --model X` and iteration 0 of `tetris-bench loop --model
X` asked the same model for the same thing with different prompts -- awkward in
a benchmark whose entire claim is that its numbers are comparable. `v3` is `v2`
plus two placeholders, so nothing in the instructions changed; only what can be
appended did.
"""

MEASUREMENT_DECLARATION = """\
## How your function will be judged

It will play one game, and you will be told: the score, lines cleared, pieces
placed, how the game ended, the number of holes left on the board, the height of
the tallest column, and how uneven the surface was. You will also be shown the
board at the end and at its worst point.

Those are the quantities measured. What they mean, and which of them matter, is
for you to work out.
"""
"""Named the measured quantities, without saying what to do about them.

It lives here rather than in `loop.py` because both the loop and one-shot
`strategy` mode need it, and `loop` already imports from this module -- putting
it the other way round would be a cycle.
"""

#: Matches a fenced code block, with or without a language tag.
CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


class StrategyError(Exception):
    """A model's reply could not be turned into a scoring function."""


def extract_code(text: str) -> str:
    """Pull the Python out of a model's reply.

    Takes the first fenced block if there is one. Falling back to the whole reply
    when there is no fence is deliberate: some models answer with bare code, and
    letting the sandbox's validator reject genuinely unusable text gives a far
    better error than a regex failure would.
    """
    if not text or not text.strip():
        raise StrategyError("the model returned an empty reply")

    match = CODE_FENCE.search(text)
    source = match.group(1) if match else text
    source = source.strip()
    if not source:
        raise StrategyError("the model returned an empty code block")
    return source + "\n"


@dataclass(frozen=True)
class GeneratedFunction:
    """A scoring function a model wrote, with the context it came from.

    Kept together because the improvement loop needs all of it: the source to
    run, the reply to debug a parse failure, and the reasoning to understand
    *why* a revision went the way it did.
    """

    source: str
    model: str
    prompt: str
    raw_reply: str
    reasoning: str = ""
    iteration: int = 0

    def save(self, directory: Path | str, stem: str) -> Path:
        """Write the function and its context to disk for later inspection.

        Two files: the source as runnable ``.py``, and everything else as
        ``.json``. The source stays readable and diffable on its own, which is
        what you want when comparing iteration 3 against iteration 4.
        """
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)

        source_path = target / f"{stem}.py"
        source_path.write_text(self.source, encoding="utf-8")
        (target / f"{stem}.json").write_text(
            json.dumps(
                {
                    "model": self.model,
                    "iteration": self.iteration,
                    "prompt": self.prompt,
                    "raw_reply": self.raw_reply,
                    "reasoning": self.reasoning,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return source_path


def build_strategy_prompt(
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    per_call_seconds: float = 1.0,
    template: str = DEFAULT_TEMPLATE,
    declare_metrics: bool = True,
    feedback_section: str = "",
) -> str:
    """Render the prompt that asks a model for a scoring function.

    The single renderer for both callers: one-shot `strategy` mode leaves
    `feedback_section` empty, and the improvement loop passes the previous
    attempt's outcome in it. Keeping one function is what makes a one-shot run
    byte-identical to the loop's iteration 0 by construction rather than by
    coincidence -- they drifted apart once already.

    The defaults match `LoopConfig`'s, so calling this with none of the extra
    arguments reproduces an iteration-0 prompt exactly.
    """
    return render(
        template,
        width=width,
        height=height,
        last_row=height - 1,
        per_call_seconds=per_call_seconds,
        measurement_section=MEASUREMENT_DECLARATION if declare_metrics else "",
        feedback_section=feedback_section,
    )


def request_scoring_function(
    client: ModelClient,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    per_call_seconds: float = 1.0,
    template: str = DEFAULT_TEMPLATE,
    iteration: int = 0,
) -> GeneratedFunction:
    """Ask a model for a scoring function and extract it from the reply."""
    prompt = build_strategy_prompt(width, height, per_call_seconds, template)
    response: ChatResponse = client.complete([{"role": "user", "content": prompt}])
    return GeneratedFunction(
        source=extract_code(response.text),
        model=response.model,
        prompt=prompt,
        raw_reply=response.text,
        reasoning=response.reasoning,
        iteration=iteration,
    )


@dataclass
class StrategyDiagnostics:
    """How much signal a scoring function actually produced.

    A function can be valid, safe, and raise on nothing while still being
    useless: if it returns the same number for every candidate, the agent cannot
    choose and degenerates into playing the first legal placement. That failure
    is invisible in a score alone -- it looks like a bad strategy rather than a
    dead function -- and ``sandbox_failures == 0`` actively suggests the function
    worked.

    These counters make it legible, and give the improvement loop something
    specific to feed back.
    """

    moves: int = 0
    flat_moves: int = 0
    unplayable: int = 0
    spread_total: float = 0.0
    #: Moves where the chosen placement was NOT the first in the list. This is
    #: the decision-relevant measure: a function can produce a non-zero spread
    #: and still never change a choice, in which case it is tie-breaking by list
    #: order rather than steering. Measuring whether spread *exists* misses that;
    #: measuring whether it ever *moves the argmax* does not.
    steering_moves: int = 0

    @property
    def flat_fraction(self) -> float:
        """Share of moves where every candidate scored identically."""
        return self.flat_moves / self.moves if self.moves else 0.0

    @property
    def mean_spread(self) -> float:
        """Average gap between the best and worst candidate, per move."""
        return self.spread_total / self.moves if self.moves else 0.0

    @property
    def steering_fraction(self) -> float:
        """Share of moves where the function chose something other than the first.

        With ~34 candidates, a function choosing at random would land on the
        first about 3% of the time, so a real strategy sits near 1.0 and an inert
        one sits at 0.0.
        """
        return self.steering_moves / self.moves if self.moves else 0.0

    @property
    def is_degenerate(self) -> bool:
        """Whether the function never actually made a decision.

        Two ways to fail, and the second was originally missed. A function can be
        flat on almost every move; or it can produce a visible spread that is far
        too small to outweigh a constant term, so the argmax never moves off the
        first candidate. The 4B's second attempt was the latter: 4 of 22 moves had
        variation -- a flat fraction of 0.82, under the old 0.95 threshold -- with
        a mean spread of 0.9 against a constant of ~1,960. Decision-equivalent to
        constant, and not flagged.
        """
        if not self.moves:
            return False
        return self.flat_fraction >= 0.95 or self.steering_moves == 0

    def summary(self) -> str:
        """One line fit for a terminal or a feedback summary."""
        if not self.moves:
            return "no moves scored"
        verdict = " (function never changed a choice)" if self.is_degenerate else ""
        return (
            f"{self.moves - self.flat_moves}/{self.moves} moves had score variation, "
            f"mean spread {self.mean_spread:.3g}, "
            f"steered {self.steering_moves}/{self.moves}{verdict}"
        )


class StrategyAgent:
    """Plays the highest-scoring placement, as judged by sandboxed model code."""

    def __init__(self, sandbox: ScoringSandbox, name: str = "strategy") -> None:
        self.name = name
        self.sandbox = sandbox
        self.diagnostics = StrategyDiagnostics()

    def choose(self, game: Game) -> Placement:
        """Score every legal placement in the sandbox and play the best.

        If every placement failed to score they are all negative infinity, and
        :func:`max` returns the first. Playing the first legal move rather than
        giving up is deliberate: a function that is broken on this particular
        board still produces a finished game with a recorded score, which is more
        informative than an aborted run.
        """
        placements = game.legal_placements()
        if not placements:
            raise ValueError("no legal placements: the game is over and should not be stepped")

        scores = self.sandbox.score(build_items(game.board, placements))
        best = max(range(len(placements)), key=lambda index: scores[index])
        self._record(scores, best)
        return placements[best]

    def _record(self, scores: list[float], chosen: int) -> None:
        """Note how much the function separated this move's candidates."""
        self.diagnostics.moves += 1
        if chosen != 0:
            self.diagnostics.steering_moves += 1
        self.diagnostics.unplayable += sum(1 for value in scores if value == UNPLAYABLE)

        playable = [value for value in scores if value != UNPLAYABLE]
        spread = max(playable) - min(playable) if len(playable) > 1 else 0.0
        self.diagnostics.spread_total += spread
        if spread == 0.0:
            self.diagnostics.flat_moves += 1
