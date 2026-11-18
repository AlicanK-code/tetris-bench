"""Tests for the model-facing text rendering."""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import legal_placements
from tetris_bench.render import (
    column_header,
    render_board,
    render_placements,
    render_state,
)


class TestColumnHeader:
    def test_counts_columns(self):
        assert column_header(10) == "0123456789"

    def test_wraps_past_nine_to_stay_one_char_per_column(self):
        """Alignment with the grid is the entire point of the header."""
        assert column_header(12) == "012345678901"
        assert len(column_header(12)) == 12

    def test_narrow_board(self):
        assert column_header(4) == "0123"


class TestRenderBoard:
    def test_empty_board_with_header(self):
        rendered = render_board(Board.empty(4, 2))
        assert rendered == "0123\n....\n...."

    def test_header_can_be_suppressed(self):
        assert render_board(Board.empty(4, 2), header=False) == "....\n...."

    def test_filled_cells_are_uniform_by_default(self):
        """Occupancy is all that can affect the next move, so identity is dropped."""
        board = Board.from_strings(["I.OO"])
        assert render_board(board, header=False) == "#.##"

    def test_show_pieces_keeps_the_letters(self):
        board = Board.from_strings(["I.OO"])
        assert render_board(board, header=False, show_pieces=True) == "I.OO"

    def test_top_row_comes_first(self):
        board = Board.from_strings(["..", "XX"])
        assert render_board(board, header=False) == "..\n##"

    def test_header_width_matches_the_grid(self):
        rendered = render_board(Board.empty(10, 3)).splitlines()
        assert all(len(line) == 10 for line in rendered)

    def test_row_count(self):
        assert len(render_board(Board.empty(10, 20)).splitlines()) == 21


class TestRenderPlacements:
    def test_numbers_each_placement_from_zero(self):
        placements = legal_placements(Board.empty(10, 20), "O")
        rendered = render_placements(placements).splitlines()
        assert len(rendered) == len(placements)
        assert rendered[0].startswith("0 ")
        assert "rot=0" in rendered[0]
        assert "col=0" in rendered[0]

    def test_reports_the_landing_row(self):
        placements = legal_placements(Board.empty(10, 20), "O")
        assert "lands row 19" in render_placements(placements)

    def test_indices_are_right_aligned_so_columns_line_up(self):
        placements = legal_placements(Board.empty(10, 20), "T")
        lines = render_placements(placements).splitlines()
        assert len(lines) == 34
        # two-digit indices mean the single-digit ones are padded
        assert lines[0].startswith(" 0")
        assert lines[33].startswith("33")

    def test_empty_list_says_so_rather_than_rendering_nothing(self):
        assert render_placements([]) == "(no legal placements)"

    def test_every_index_is_usable_to_select_a_placement(self):
        """The index is the answer format, so it must map back exactly."""
        placements = legal_placements(Board.empty(10, 20), "J")
        lines = render_placements(placements).splitlines()
        for index, line in enumerate(lines):
            assert line.strip().startswith(str(index))


class TestRenderState:
    def test_includes_the_grid_and_the_metadata(self):
        game = Game(seed=1)
        rendered = render_state(game)
        assert "0123456789" in rendered
        assert f"current piece   {game.current}" in rendered
        assert "next pieces" in rendered
        assert "score           0" in rendered
        assert "pieces placed   0" in rendered

    def test_reports_board_features(self):
        game = Game(seed=1)
        rendered = render_state(game)
        assert "max height      0" in rendered
        assert "holes           0" in rendered
        assert "bumpiness       0" in rendered

    def test_does_not_mention_a_hold_piece(self):
        """The engine has no hold mechanic, so the prompt must not imply one."""
        assert "hold" not in render_state(Game(seed=1)).lower()

    def test_placements_are_omitted_by_default(self):
        assert "legal placements" not in render_state(Game(seed=1))

    def test_placements_can_be_included(self):
        rendered = render_state(Game(seed=1), show_placements=True)
        assert "legal placements:" in rendered
        assert "rot=" in rendered

    def test_next_pieces_are_space_separated(self):
        game = Game(seed=1, preview=3)
        assert f"next pieces     {' '.join(game.next_pieces)}" in render_state(game)

    @pytest.mark.parametrize("show_pieces", [True, False])
    def test_renders_after_play(self, show_pieces):
        from tetris_bench.agents.heuristic import heuristic_agent
        from tetris_bench.runner import play_game

        game = Game(seed=1, max_pieces=20)
        play_game(game, heuristic_agent())
        rendered = render_state(game, show_pieces=show_pieces)
        assert "pieces placed   20" in rendered
