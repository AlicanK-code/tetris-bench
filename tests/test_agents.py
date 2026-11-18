"""Tests for the baseline agents and the scoring-function abstraction."""

import pytest

from tetris_bench.agents.base import ScoringAgent
from tetris_bench.agents.heuristic import (
    DEFAULT_WEIGHTS,
    HeuristicWeights,
    heuristic_agent,
    heuristic_scorer,
)
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.engine.pieces import PIECES
from tetris_bench.engine.rng import SevenBag
from tetris_bench.metrics import holes
from tetris_bench.runner import play_game


class TestScoringAgent:
    def test_picks_the_highest_scoring_placement(self):
        game = Game(seed=1)
        target = game.legal_placements()[3]
        agent = ScoringAgent(lambda _board, p: 1.0 if p == target else 0.0)
        assert agent.choose(game) == target

    def test_ties_break_to_the_first_placement(self):
        """Arbitrary but deterministic, which is what reproducibility needs."""
        game = Game(seed=1)
        agent = ScoringAgent(lambda _board, _p: 0.0)
        assert agent.choose(game) == game.legal_placements()[0]

    def test_carries_a_name_for_logging(self):
        assert ScoringAgent(lambda _b, _p: 0.0, name="custom").name == "custom"

    def test_scorer_receives_the_current_board(self):
        game = Game(seed=1)
        seen: list[Board] = []

        def scorer(board, _placement):
            seen.append(board)
            return 0.0

        ScoringAgent(scorer).choose(game)
        assert seen and all(board == game.board for board in seen)


class TestRandomAgent:
    def test_chooses_a_legal_placement(self):
        game = Game(seed=1)
        assert RandomAgent(seed=0).choose(game) in game.legal_placements()

    def test_same_seeds_reproduce_the_same_game(self):
        def play(agent_seed):
            return play_game(Game(seed=5, max_pieces=40), RandomAgent(seed=agent_seed), agent_seed)

        assert play(0) == play(0)

    def test_agent_seed_changes_play(self):
        def play(agent_seed):
            return play_game(Game(seed=5, max_pieces=40), RandomAgent(seed=agent_seed), agent_seed)

        assert play(0) != play(1)

    def test_agent_randomness_does_not_disturb_the_piece_sequence(self):
        """The guard against sharing one RNG between the bag and the agent.

        If they shared a stream, the agent's draws would shift the pieces and two
        agents would face different games -- destroying the premise that every
        model plays identical seeds.
        """
        expected = SevenBag(seed=5).peek(60)
        for agent_seed in (0, 1, 2, 99):
            game = Game(seed=5, max_pieces=40)
            play_game(game, RandomAgent(seed=agent_seed), agent_seed)
            assert SevenBag(seed=5).peek(60) == expected

    def test_reports_its_name_and_seed(self):
        agent = RandomAgent(seed=7)
        assert agent.name == "random"
        assert agent.seed == 7


class TestHeuristicScorer:
    def test_prefers_a_flat_i_placement_to_an_upright_one(self):
        """Lying the I piece down keeps the stack low and smooth."""
        board = Board.empty(10, 20)
        score = heuristic_scorer()
        game = Game(seed=1)
        game.board = board
        game.current = "I"
        flat = next(p for p in game.legal_placements() if PIECES["I"].height(p.rotation) == 1)
        upright = next(p for p in game.legal_placements() if PIECES["I"].height(p.rotation) == 4)
        assert score(board, flat) > score(board, upright)

    def test_rewards_clearing_a_line(self):
        board = Board.from_strings(["." * 10] * 19 + ["." + "X" * 9])
        game = Game(seed=1)
        game.board = board
        game.current = "I"
        score = heuristic_scorer()
        clears = next(
            p
            for p in game.legal_placements()
            if p.column == 0 and PIECES["I"].height(p.rotation) == 4
        )
        elsewhere = next(p for p in game.legal_placements() if p.column == 5)
        assert score(board, clears) > score(board, elsewhere)

    def test_avoids_creating_a_hole(self):
        # A one-wide notch at column 0: filling it flat would bridge over the gap.
        board = Board.from_strings(["." * 4] * 3 + [".XXX"])
        game = Game(seed=1)
        game.board = board
        game.current = "O"
        score = heuristic_scorer()
        best = max(game.legal_placements(), key=lambda p: score(board, p))
        from tetris_bench.engine.placements import apply_placement

        after, _ = apply_placement(board, best)
        assert holes(after) == 0

    def test_weights_are_configurable(self):
        """Rewarding bumpiness instead of punishing it flips the I preference.

        Note aggregate height cannot be used to tell these two apart: four cells
        is four cells, whether stacked in one column or spread across four.
        Bumpiness is what actually distinguishes them -- an upright I leaves a
        height-4 cliff, a flat I leaves a height-1 step.
        """
        inverted = HeuristicWeights(
            aggregate_height=0.0, complete_lines=0.0, holes=0.0, bumpiness=+1.0
        )
        board = Board.empty(10, 20)
        game = Game(seed=1)
        game.current = "I"
        flat = next(p for p in game.legal_placements() if PIECES["I"].height(p.rotation) == 1)
        upright = next(p for p in game.legal_placements() if PIECES["I"].height(p.rotation) == 4)
        score = heuristic_scorer(inverted)
        assert score(board, upright) > score(board, flat)

    def test_default_weights_are_the_el_tetris_values(self):
        assert (
            HeuristicWeights(
                aggregate_height=-0.510066,
                complete_lines=0.760666,
                holes=-0.356630,
                bumpiness=-0.184483,
            )
            == DEFAULT_WEIGHTS
        )

    def test_weights_are_frozen(self):
        with pytest.raises(AttributeError):
            DEFAULT_WEIGHTS.holes = 0.0


class TestHeuristicAgent:
    def test_is_deterministic(self):
        def play():
            return play_game(Game(seed=3, max_pieces=80), heuristic_agent())

        assert play() == play()

    def test_is_named_for_logging(self):
        assert heuristic_agent().name == "heuristic"

    @pytest.mark.parametrize("seed", [1, 2, 17, 123])
    def test_beats_the_random_agent(self, seed):
        heuristic = play_game(Game(seed=seed, max_pieces=200), heuristic_agent())
        random_play = play_game(Game(seed=seed, max_pieces=200), RandomAgent(seed=0), 0)
        assert heuristic.score > random_play.score
        assert heuristic.pieces_placed > random_play.pieces_placed

    @pytest.mark.parametrize("seed", [1, 2, 17, 123])
    def test_survives_the_piece_budget(self, seed):
        """A competent heuristic should not die inside 200 pieces.

        This is the engine sanity check: if it blocks out early, the likely cause
        is the scorer measuring the board before the placement rather than after.
        """
        result = play_game(Game(seed=seed, max_pieces=200), heuristic_agent())
        assert result.cause == "piece_limit"
        assert result.pieces_placed == 200
        assert result.final_holes <= 4
