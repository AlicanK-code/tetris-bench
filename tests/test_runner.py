"""Tests for the game runner and its result record."""

import json

import pytest

from tetris_bench.agents.heuristic import heuristic_agent
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.engine.game import Game
from tetris_bench.records import GameResult
from tetris_bench.runner import play_game


def test_plays_until_the_game_is_over():
    game = Game(seed=1, max_pieces=25)
    result = play_game(game, heuristic_agent())
    assert game.over
    assert result.pieces_placed == 25
    assert result.cause == "piece_limit"


def test_result_mirrors_the_finished_game():
    game = Game(seed=2, max_pieces=30)
    result = play_game(game, heuristic_agent())
    assert result.score == game.score
    assert result.lines_cleared == game.lines_cleared
    assert result.pieces_placed == game.pieces_placed
    assert result.cause == game.cause
    assert result.seed == game.seed


def test_records_the_agent_name_and_seed():
    result = play_game(Game(seed=1, max_pieces=10), RandomAgent(seed=4), agent_seed=4)
    assert result.agent == "random"
    assert result.agent_seed == 4


def test_deterministic_agents_report_no_agent_seed():
    result = play_game(Game(seed=1, max_pieces=10), heuristic_agent())
    assert result.agent_seed is None


def test_avg_max_height_is_sampled_across_the_game():
    """Averaged per placement, so it differs from the final height."""
    result = play_game(Game(seed=1, max_pieces=60), heuristic_agent())
    assert result.avg_max_height > 0
    assert result.avg_max_height != result.final_max_height


def test_avg_max_height_is_reported_for_a_game_that_dies_early():
    """A game can block out on a narrow board, so the average still has to hold."""
    game = Game(seed=4, width=5, height=8, max_pieces=None)
    result = play_game(game, RandomAgent(seed=1), agent_seed=1)
    assert result.cause == "block_out"
    assert result.pieces_placed > 0
    assert result.avg_max_height > 0


def test_result_is_frozen():
    result = play_game(Game(seed=1, max_pieces=5), heuristic_agent())
    with pytest.raises(AttributeError):
        result.score = 0


def test_as_dict_is_json_serialisable():
    """The record has to survive a trip through JSONL."""
    result = play_game(Game(seed=1, max_pieces=5), heuristic_agent())
    payload = result.as_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert set(payload) == set(GameResult.__dataclass_fields__)
