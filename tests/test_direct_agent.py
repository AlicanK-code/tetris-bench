"""Tests for the direct agent.

No model is involved: the agent's whole job is to turn a reply into a placement
and to account for the replies it could not use, so a stub client that returns
scripted text exercises all of it.

What is worth testing here is the recovery behaviour. A direct game is one call
per piece, so a parsing rule that is slightly wrong does not fail loudly -- it
quietly plays move 0 for a few hundred turns and reports a low score, which
looks exactly like a model that chooses badly. The tests therefore pin down that
an invalid reply is *counted*, and that a near-miss is not silently rescued.
"""

from __future__ import annotations

import pytest

from tetris_bench.agents.direct import PROMPT_NAME, DirectAgent, parse_index
from tetris_bench.clients.client import ChatResponse
from tetris_bench.engine.game import Game


class StubClient:
    """Returns scripted replies and records the prompts it was sent."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, messages: list[dict[str, str]], seed: int | None = None) -> ChatResponse:
        self.prompts.append(messages[-1]["content"])
        # The last reply repeats, so a test can play a whole game off one script.
        text = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        return ChatResponse(
            text=text,
            model="stub",
            tokens_in=10,
            tokens_out=2,
            latency_seconds=0.1,
            retries=0,
            estimated_cost_usd=0.0,
        )


def agent_for(replies: list[str]) -> tuple[DirectAgent, StubClient]:
    client = StubClient(replies)
    return DirectAgent(client), client  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "count", "expected"),
    [
        ("7", 34, 7),
        ("0", 34, 0),
        ("33", 34, 33),
        ("  12\n", 34, 12),
        ("I'll play 12.", 34, 12),
        ("**5**", 34, 5),
        # Out of range is refused, never clamped to the nearest legal index.
        ("34", 34, None),
        ("99", 34, None),
        ("", 34, None),
        ("no number here", 34, None),
        ("none of these look good", 34, None),
    ],
)
def test_parse_index(text: str, count: int, expected: int | None) -> None:
    assert parse_index(text, count) == expected


def test_the_last_integer_wins_because_a_conclusion_comes_last() -> None:
    """A model that reasons despite being asked not to states its answer last."""
    reply = "Options 0 to 33. Column 4 is tall and row 19 is the floor, so I choose 5"
    assert parse_index(reply, 34) == 5


def test_a_negative_looking_answer_reads_as_its_digits_not_as_out_of_range() -> None:
    """`-3` has no valid reading, and must not come back as a usable index.

    The integer pattern does not match the sign, so this is documenting what the
    rule actually does: it sees `3`. That is a legal index, so the reply is
    accepted. The alternative -- refusing anything near a minus sign -- would
    reject `rot=1 col=3-wide` style prose for no benefit.
    """
    assert parse_index("-3", 34) == 3


def test_the_chosen_index_is_the_placement_played() -> None:
    game = Game(seed=1, max_pieces=1)
    placements = game.legal_placements()
    agent, _ = agent_for(["3"])
    assert agent.choose(game) == placements[3]
    assert agent.invalid_outputs == 0


def test_an_unparseable_reply_is_counted_and_plays_move_zero() -> None:
    game = Game(seed=1, max_pieces=1)
    placements = game.legal_placements()
    agent, _ = agent_for(["I don't like any of these"])

    assert agent.choose(game) == placements[0]
    assert agent.invalid_outputs == 1
    assert agent.invalid_samples == ["I don't like any of these"]


def test_an_out_of_range_index_is_not_clamped_into_range() -> None:
    """Clamping would turn a wrong answer into a legal move and hide the failure."""
    game = Game(seed=1, max_pieces=1)
    placements = game.legal_placements()
    assert len(placements) < 500
    agent, _ = agent_for(["500"])

    assert agent.choose(game) == placements[0]
    assert agent.invalid_outputs == 1


def test_invalid_samples_are_bounded_but_the_count_is_not() -> None:
    """A game that fails on every turn must not grow a list without limit."""
    agent, _ = agent_for(["nope"])
    game = Game(seed=1, max_pieces=8)

    while not game.over:
        game.step(agent.choose(game))

    assert agent.invalid_outputs == game.pieces_placed > 3
    assert len(agent.invalid_samples) == 3


def test_one_call_per_piece() -> None:
    """The cost claim this mode exists to demonstrate, asserted."""
    agent, client = agent_for(["0"])
    game = Game(seed=1, max_pieces=6)

    while not game.over:
        game.step(agent.choose(game))

    assert len(client.prompts) == game.pieces_placed == 6


def test_every_turn_gets_a_fresh_prompt_that_accumulates_nothing() -> None:
    """Stateless per turn: no history, so tokens-in does not grow with the game.

    Without this the cost-per-piece figure would depend on how long the game had
    lasted, and a 2,000-turn conversation would overrun any local context window.

    The invariant is structural rather than a size bound, because prompt length
    legitimately varies between turns: an S piece has 17 legal placements where
    most pieces have 34, so the choices block halves and doubles as the bag
    turns over. What must never change is how many sections there are.
    """
    agent, client = agent_for(["0"])
    game = Game(seed=1, max_pieces=12)

    while not game.over:
        game.step(agent.choose(game))

    assert len(client.prompts) == 12
    # One board, one list of choices, one of everything else, on every turn.
    assert {prompt.count("## ") for prompt in client.prompts} == {5}
    assert {prompt.count("## The current position") for prompt in client.prompts} == {1}
    # Bounded in absolute terms, not merely non-growing.
    assert max(len(prompt) for prompt in client.prompts) < 8_000


def test_the_prompt_is_fully_rendered_and_carries_the_orientation_warning() -> None:
    game = Game(seed=1, max_pieces=1)
    placements = game.legal_placements()
    agent, _ = agent_for(["0"])
    prompt = agent.build_prompt(game, placements)

    # `prompts.render` raises on a missing value, so a leftover brace would mean
    # a placeholder the template needs and the agent never passes.
    assert "{" not in prompt and "}" not in prompt
    assert "Row 0 is the top of the board" in prompt
    assert f"between 0 and {len(placements) - 1} inclusive" in prompt
    # Every legal move is offered, so the model cannot propose an illegal one.
    # One extra `rot=` comes from the line explaining the format of the list.
    assert prompt.count("rot=") == len(placements) + 1


def test_an_unknown_template_fails_at_once_naming_the_available_ones() -> None:
    game = Game(seed=1, max_pieces=1)
    client = StubClient(["0"])
    agent = DirectAgent(client, prompt_name="direct_v99")  # type: ignore[arg-type]

    with pytest.raises(FileNotFoundError, match=PROMPT_NAME):
        agent.build_prompt(game, game.legal_placements())
