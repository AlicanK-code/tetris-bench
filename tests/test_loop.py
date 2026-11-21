"""Tests for the improvement loop and the feedback summary.

No network and no local model: the client is faked, so the whole
feedback-revise-replay cycle is exercised deterministically.
"""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.feedback import SnapshotCollector, build_feedback
from tetris_bench.jsonl import read_records
from tetris_bench.loop import (
    LoopConfig,
    Position,
    build_prompt,
    completed_positions,
    empty_result,
    feedback_text,
    play_function,
    positions,
    run_loop,
)
from tetris_bench.records import ModelUsage
from tetris_bench.runner import play_game

CONSTANT = "def score(board, placement):\n    return 1.0\n"

HOLES_ONLY = """
def score(board, placement):
    holes = 0
    for c in range(10):
        seen = False
        for r in range(20):
            if board[r][c]:
                seen = True
            elif seen:
                holes += 1
    return float(placement["lines_cleared"]) * 10 - holes
"""

GOOD = """
def score(board, placement):
    h = [0] * 10
    holes = 0
    for c in range(10):
        seen = False
        for r in range(20):
            if board[r][c]:
                if not seen:
                    h[c] = 20 - r
                    seen = True
            elif seen:
                holes += 1
    bump = sum(abs(h[i] - h[i + 1]) for i in range(9))
    return -0.51 * sum(h) + 0.76 * placement["lines_cleared"] - 0.36 * holes - 0.18 * bump
"""

BROKEN = "import os\ndef score(board, placement):\n    return 1.0\n"


class FakeClient:
    """Returns a scripted sequence of functions, recording every prompt."""

    def __init__(self, sources, reply_template="```python\n{}\n```"):
        self.sources = list(sources)
        self.prompts: list[str] = []
        self.reply_template = reply_template
        self.config = type("C", (), {"name": "fake", "model": "fake"})()
        self._usage = ModelUsage()

    @property
    def usage(self):
        return self._usage

    def reset_usage(self):
        self._usage = ModelUsage()

    def complete(self, messages, seed=None):
        self.prompts.append(messages[-1]["content"])
        source = self.sources.pop(0) if self.sources else GOOD
        self._usage = ModelUsage(model_calls=1, tokens_in=100, tokens_out=500)
        template = self.reply_template

        class Response:
            text = template.format(source)
            reasoning = "thinking"
            model = "fake"

        return Response()


@pytest.fixture
def config(tmp_path):
    return LoopConfig(
        model="fake",
        train_seeds=(1,),
        eval_seeds=(),
        iterations=3,
        chains=1,
        max_pieces=120,
        log_path=tmp_path / "loop.jsonl",
        functions_dir=tmp_path / "funcs",
    )


class TestPositions:
    def test_covers_the_whole_sweep(self):
        """A position is a (chain, iteration); seeds are played within one."""
        cfg = LoopConfig(model="m", train_seeds=(1, 2), iterations=3, chains=2)
        assert len(list(positions(cfg))) == 6

    def test_iterations_are_contiguous_within_a_chain(self):
        """Iterations are sequential; chains and seeds are independent."""
        cfg = LoopConfig(model="m", train_seeds=(1,), iterations=3, chains=2)
        order = [(p.chain, p.iteration) for p in positions(cfg)]
        assert order == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]

    def test_stem_identifies_a_position_uniquely(self):
        stems = {Position(c, i).stem("m") for c in (0, 1) for i in (0, 1)}
        assert len(stems) == 4

    def test_stem_is_readable(self):
        assert Position(1, 4).stem("qwen3-14b") == "qwen3-14b-chain1-iter4"


class TestPlayFunction:
    def test_plays_a_working_function(self, config):
        outcome = play_function(GOOD, 1, config)
        assert not outcome.rejected
        assert outcome.result is not None
        assert outcome.score > 0
        assert outcome.final_board is not None

    def test_records_a_rejection_without_playing(self, config):
        outcome = play_function(BROKEN, 1, config)
        assert outcome.rejected
        assert "imports are not allowed" in outcome.reason
        assert outcome.result is None
        assert outcome.score == 0

    def test_collects_snapshots(self, config):
        outcome = play_function(CONSTANT, 1, config)
        assert outcome.collector is not None
        # worst_holes starts at -1, so these are what distinguish "the collector
        # ran" from "it was never called".
        assert outcome.collector.worst_board is not None
        assert outcome.collector.worst_piece > 0
        assert outcome.collector.worst_holes > 0

    def test_a_constant_function_is_flagged(self, config):
        outcome = play_function(CONSTANT, 1, config)
        assert outcome.diagnostics.is_degenerate


class TestFeedbackText:
    def test_reports_the_outcome(self, config):
        text = feedback_text(play_function(GOOD, 1, config), config)
        assert "How your function played" in text
        assert "score:" in text
        assert "lines cleared:" in text

    def test_reports_board_quality(self, config):
        text = feedback_text(play_function(GOOD, 1, config), config)
        assert "holes at the end" in text
        assert "tallest column" in text

    def test_includes_a_board_snapshot(self, config):
        text = feedback_text(play_function(GOOD, 1, config), config)
        assert "the final position" in text
        assert "0123456789" in text

    def test_names_a_constant_function_as_a_mechanical_fact(self, config):
        """A model told only 'you scored 0' cannot tell a bad strategy from
        arithmetic that never varied, and those need different fixes."""
        text = feedback_text(play_function(CONSTANT, 1, config), config)
        assert "same score for every candidate" in text

    def test_explains_a_rejection_instead_of_results(self, config):
        text = feedback_text(play_function(BROKEN, 1, config), config)
        assert "rejected before it could run" in text
        assert "imports are not allowed" in text
        assert "How your function played" not in text

    def test_gives_the_reference_score_for_scale(self, config):
        text = feedback_text(play_function(GOOD, 1, config), config)
        assert "21600" in text

    def test_withholds_our_diagnosis(self, config):
        """Symptoms, not diagnoses: the model must find its own bug.

        Otherwise the curve partly measures our tooling rather than the model.
        The feedback deliberately says "surface unevenness" rather than naming
        the feature, so that a model has not been handed the vocabulary.
        """
        text = feedback_text(play_function(HOLES_ONLY, 1, config), config).lower()
        assert "bumpiness" not in text
        assert "surface unevenness" in text

    def test_reports_hole_counts_without_naming_a_cause(self, config):
        """The number is a symptom; why it is high is the model's problem."""
        text = feedback_text(play_function(HOLES_ONLY, 1, config), config)
        assert "holes at the end" in text
        for leak in ("your hole count", "because", "try penalising", "should penalise"):
            assert leak not in text.lower()


class TestRunLoop:
    def test_produces_one_record_per_iteration(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        assert len(list(read_records(config.log_path))) == 3

    def test_records_the_curve(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        rows = list(read_records(config.log_path))
        assert [row["iteration"] for row in rows] == [0, 1, 2]
        assert rows[0]["score"] == 0
        assert rows[2]["score"] > rows[1]["score"] > rows[0]["score"]

    def test_each_row_ties_back_to_its_saved_function(self, config):
        """Resume depends on the log and the artifacts agreeing."""
        import hashlib

        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        for row in read_records(config.log_path):
            stem = Position(row["chain"], row["iteration"]).stem("fake")
            source = (config.functions_dir / f"{stem}.py").read_text()
            assert row["function_sha"] == hashlib.sha256(source.encode()).hexdigest()[:12]

    def test_saves_every_function_to_disk(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        for iteration in range(3):
            stem = Position(0, iteration).stem("fake")
            assert (config.functions_dir / f"{stem}.py").exists()
            assert (config.functions_dir / f"{stem}.json").exists()

    def test_the_first_iteration_uses_the_initial_template(self, config):
        client = FakeClient([CONSTANT, HOLES_ONLY, GOOD])
        run_loop(client, config, on_progress=None)
        assert "scoring candidate moves" in client.prompts[0]
        assert "How your function played" not in client.prompts[0]

    def test_later_iterations_carry_feedback_and_the_prior_function(self, config):
        client = FakeClient([CONSTANT, HOLES_ONLY, GOOD])
        run_loop(client, config, on_progress=None)
        revision = client.prompts[1]
        assert "How your function played" in revision
        assert "The function you wrote" in revision
        assert "return 1.0" in revision

    def test_records_diagnostics(self, config):
        run_loop(FakeClient([CONSTANT, GOOD, GOOD]), config, on_progress=None)
        rows = list(read_records(config.log_path))
        assert rows[0]["flat_moves"] == rows[0]["scored_moves"]
        assert rows[1]["flat_moves"] < rows[1]["scored_moves"]

    def test_records_a_function_hash(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        shas = [row["function_sha"] for row in read_records(config.log_path)]
        assert len(set(shas)) == 3
        assert all(sha for sha in shas)

    def test_a_rejected_function_counts_as_an_invalid_output(self, config):
        run_loop(FakeClient([BROKEN, GOOD, GOOD]), config, on_progress=None)
        rows = list(read_records(config.log_path))
        assert rows[0]["invalid_outputs"] == 1
        assert rows[0]["score"] == 0
        assert rows[1]["invalid_outputs"] == 0

    def test_a_rejection_does_not_stop_the_loop(self, config):
        run_loop(FakeClient([BROKEN, GOOD, GOOD]), config, on_progress=None)
        assert len(list(read_records(config.log_path))) == 3

    def test_an_unparseable_reply_is_logged_as_an_invalid_output(self, config):
        """CLAUDE.md lists invalid outputs as a per-game metric, so it needs a row.

        Skipping the position silently would also break resume, which works out
        where it is from the log.
        """
        client = FakeClient([CONSTANT, GOOD, GOOD], reply_template="")
        run_loop(client, config, on_progress=None)
        rows = list(read_records(config.log_path))
        assert len(rows) == 3
        assert all(row["invalid_outputs"] == 1 for row in rows)
        assert all(row["score"] == 0 for row in rows)
        assert all(row["played"] is False for row in rows)
        assert len(client.prompts) == 3

    def test_an_unparseable_reply_keeps_the_chain_s_previous_function(self, config):
        """Otherwise the next iteration is shown an empty code block.

        The chain would silently restart while still being numbered a
        continuation, which corrupts the curve it is supposed to produce.
        """
        client = FakeClient([GOOD, "", GOOD], reply_template="{}")
        client.sources = [f"```python\n{GOOD}\n```", "", f"```python\n{GOOD}\n```"]
        run_loop(client, config, on_progress=None)
        third = client.prompts[2]
        assert "```python\n```" not in third
        assert "lines_cleared" in third

    def test_chains_are_independent(self, tmp_path):
        """A chain must never see another chain's function."""
        config = LoopConfig(
            model="fake",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=2,
            chains=2,
            max_pieces=60,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )
        client = FakeClient([CONSTANT, GOOD, CONSTANT, GOOD])
        run_loop(client, config, on_progress=None)
        # Each chain's first prompt is the initial one, not a revision.
        assert "How your function played" not in client.prompts[0]
        assert "How your function played" not in client.prompts[2]
        assert "How your function played" in client.prompts[1]
        assert "How your function played" in client.prompts[3]

    def test_records_the_chain_index(self, tmp_path):
        config = LoopConfig(
            model="fake",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=1,
            chains=3,
            max_pieces=40,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )
        run_loop(FakeClient([GOOD, GOOD, GOOD]), config, on_progress=None)
        assert sorted(row["chain"] for row in read_records(config.log_path)) == [0, 1, 2]


class TestResume:
    def test_completed_positions_are_read_from_the_log(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        assert completed_positions(config.log_path, "fake", (1,)) == {(0, 0), (0, 1), (0, 2)}

    def test_a_missing_log_means_nothing_is_done(self, tmp_path):
        assert completed_positions(tmp_path / "nope.jsonl", "fake", (1,)) == set()

    def test_rerunning_makes_no_model_calls(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        resumed = FakeClient([GOOD])
        run_loop(resumed, config, on_progress=None)
        assert resumed.prompts == []

    def test_rerunning_adds_no_records(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        run_loop(FakeClient([GOOD]), config, on_progress=None)
        assert len(list(read_records(config.log_path))) == 3

    def test_a_partial_run_resumes_where_it_stopped(self, tmp_path):
        short = LoopConfig(
            model="fake",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=1,
            chains=1,
            max_pieces=60,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )
        run_loop(FakeClient([CONSTANT]), short, on_progress=None)

        longer = LoopConfig(**{**short.__dict__, "iterations": 3})
        client = FakeClient([HOLES_ONLY, GOOD])
        run_loop(client, longer, on_progress=None)

        assert len(client.prompts) == 2  # only the two new iterations
        assert len(list(read_records(longer.log_path))) == 3

    def test_resume_replays_the_saved_function_for_feedback(self, tmp_path):
        """The log says where we are; the saved function regenerates feedback."""
        short = LoopConfig(
            model="fake",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=1,
            chains=1,
            max_pieces=60,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )
        run_loop(FakeClient([CONSTANT]), short, on_progress=None)

        longer = LoopConfig(**{**short.__dict__, "iterations": 2})
        client = FakeClient([GOOD])
        run_loop(client, longer, on_progress=None)

        # The revision prompt must contain the replayed game's feedback and the
        # function from disk, not a placeholder.
        assert "How your function played" in client.prompts[0]
        assert "return 1.0" in client.prompts[0]

    def test_a_different_model_does_not_count_as_done(self, config):
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        assert completed_positions(config.log_path, "other", (1,)) == set()


class TestSnapshotCollector:
    def test_keeps_the_worst_board(self):
        game = Game(seed=1, max_pieces=40)
        collector = SnapshotCollector()
        from tetris_bench.agents.strategy import StrategyAgent
        from tetris_bench.sandbox import ScoringSandbox

        with ScoringSandbox(CONSTANT) as sandbox:
            play_game(game, StrategyAgent(sandbox), on_step=collector)
        assert collector.worst_board is not None
        assert collector.worst_holes > 0
        assert collector.worst_piece > 0

    def test_returns_both_snapshots_when_they_differ(self):
        collector = SnapshotCollector()
        # One block at the top of column 0 leaves 19 covered cells beneath it.
        board = Board.from_strings(["X" + "." * 9] + ["." * 10] * 19)
        collector(type("G", (), {"board": board, "pieces_placed": 5})())
        shots = collector.snapshots(Board.empty(10, 20))
        assert len(shots) == 2
        assert "after 5 pieces" in shots[0][0]
        assert "19 holes" in shots[0][0]
        assert shots[1][0] == "the final position"
        assert collector.worst_piece == 5

    def test_does_not_repeat_the_final_board(self):
        collector = SnapshotCollector()
        final = Board.empty(10, 20)
        collector(type("G", (), {"board": final, "pieces_placed": 1})())
        shots = collector.snapshots(final)
        assert len(shots) == 1


def test_empty_result_is_all_zeros():
    result = empty_result("strategy", 7)
    assert result.score == 0
    assert result.pieces_placed == 0
    assert result.seed == 7
    assert result.cause is None


def test_build_feedback_without_a_collector_still_shows_the_final_board():
    game = Game(seed=1, max_pieces=10)
    from tetris_bench.agents.heuristic import heuristic_agent

    result = play_game(game, heuristic_agent())
    from tetris_bench.agents.strategy import StrategyDiagnostics

    feedback = build_feedback(result, StrategyDiagnostics(), game.board)
    assert len(feedback.snapshots) == 1
    assert "the final position" in feedback.render()


#: Reproduces a real composed failure. A broad `except Exception:` inside a loop
#: is an ordinary defensive pattern; it passes AST validation, and it used to
#: swallow the sandbox's own SIGALRM timeout, wedge the worker, and abort the
#: whole sweep. See CallTimeout's docstring in sandbox_worker.
WEDGE = """
def score(board, placement):
    while True:
        try:
            x = 0
            for i in range(100000):
                x += i
        except Exception:
            pass
"""


class TestWedgeContainment:
    def test_the_wedge_passes_ast_validation(self):
        """Layer 1 cannot refuse it: there is nothing forbidden in the source."""
        from tetris_bench.sandbox import validate_source

        validate_source(WEDGE)

    def test_model_code_cannot_swallow_its_own_timeout(self):
        """CallTimeout derives from BaseException precisely so this cannot work."""
        from tetris_bench.sandbox import UNPLAYABLE, SandboxLimits, ScoringSandbox

        limits = SandboxLimits(per_call_seconds=0.2, per_batch_seconds=10.0)
        with ScoringSandbox(WEDGE, limits=limits) as sandbox:
            scores = sandbox.score(
                [{"board": [[False] * 10] * 20, "placement": {"lines_cleared": 0}}]
            )
            assert scores == [UNPLAYABLE]
            assert sandbox.failures == 1
            assert "CallTimeout" in sandbox.errors[0]

    def test_a_crash_is_recorded_rather_than_raised(self, config):
        """One wedged function must not cost every remaining seed and chain."""
        import dataclasses

        from tetris_bench.sandbox import SandboxCrashed

        tiny = dataclasses.replace(config, per_call_seconds=0.05)
        try:
            outcome = play_function(WEDGE, 1, tiny)
        except SandboxCrashed:  # pragma: no cover - the bug this guards against
            pytest.fail("SandboxCrashed escaped play_function and would end the sweep")
        assert outcome.result is not None or outcome.crashed

    def test_crash_feedback_explains_the_time_limit(self, config):
        from tetris_bench.loop import Outcome

        text = feedback_text(Outcome(source=WEDGE, crashed=True, reason="no answer"), config)
        assert "stopped responding" in text
        assert "catching exceptions broadly will not rescue you" in text

    def test_a_crash_is_visible_in_the_log(self, config):
        from tetris_bench.loop import Outcome, _record

        record = _record(
            Position(0, 0), config, Outcome(source="x", crashed=True), ModelUsage(), 1, "train"
        )
        assert record.as_dict()["sandbox_failures"] >= 1
        assert record.as_dict()["score"] == 0


class TestLogRobustness:
    def test_a_truncated_final_line_is_tolerated(self, config):
        """A run killed mid-write is exactly why the format is JSONL."""
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        with config.log_path.open("a") as handle:
            handle.write('{"model": "fake", "mode": "str')
        assert completed_positions(config.log_path, "fake", (1,)) == {(0, 0), (0, 1), (0, 2)}
        assert len(list(read_records(config.log_path))) == 3

    def test_a_logged_position_with_no_saved_function_is_an_explicit_error(self, config):
        """Falling through would append a second row for the same position."""
        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        (config.functions_dir / f"{Position(0, 1).stem('fake')}.py").unlink()
        with pytest.raises(RuntimeError, match="is missing"):
            run_loop(FakeClient([GOOD]), config, on_progress=None)
        # and nothing was appended
        assert len(list(read_records(config.log_path))) == 3

    def test_two_models_share_one_log_without_interfering(self, config):
        import dataclasses

        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        other = dataclasses.replace(config, model="other")
        client = FakeClient([CONSTANT, HOLES_ONLY, GOOD])
        run_loop(client, other, on_progress=None)

        rows = list(read_records(config.log_path))
        assert len(rows) == 6
        assert sum(1 for r in rows if r["model"] == "fake") == 3
        assert sum(1 for r in rows if r["model"] == "other") == 3
        assert "How your function played" not in client.prompts[0]

    def test_widening_chains_runs_the_new_chain_fresh(self, config):
        import dataclasses

        run_loop(FakeClient([CONSTANT, HOLES_ONLY, GOOD]), config, on_progress=None)
        wider = dataclasses.replace(config, chains=2)
        client = FakeClient([CONSTANT, HOLES_ONLY, GOOD])
        run_loop(client, wider, on_progress=None)

        assert len(client.prompts) == 3  # chain 0 skipped, chain 1 run in full
        assert "How your function played" not in client.prompts[0]
        assert len(list(read_records(config.log_path))) == 6


def test_a_game_that_never_ran_renders_a_sentence_not_none():
    """`cause` is None for a rejected function, and the model reads this text."""
    from tetris_bench.agents.strategy import StrategyDiagnostics
    from tetris_bench.engine.board import Board

    feedback = build_feedback(
        empty_result("strategy", 1), StrategyDiagnostics(), Board.empty(10, 20)
    )
    text = feedback.render()
    assert "how it ended: the game did not run" in text
    assert "None" not in text


class TestPromptIsAPureInsertion:
    """The iteration 0 -> 1 step must change the feedback and nothing else.

    Previously iteration 0 used `strategy_v2` and later ones `revise_v1`, which
    differed in several ways simultaneously: the measurement vocabulary appeared
    for the first time, the board-orientation note was dropped, and the worked
    example went away. A rise at that step was therefore unattributable. Now one
    template serves every iteration and the feedback block is simply empty on the
    first, so the only delta is the feedback.
    """

    def prompts(self, config):
        first = build_prompt(config, None)
        second = build_prompt(config, play_function(CONSTANT, 1, config))
        return first, second

    def test_nothing_is_removed_when_feedback_is_added(self, config):
        first, second = self.prompts(config)
        head, tail = 0, 0
        f, s = first.splitlines(), second.splitlines()
        while head < min(len(f), len(s)) and f[head] == s[head]:
            head += 1
        while tail < min(len(f), len(s)) - head and f[-1 - tail] == s[-1 - tail]:
            tail += 1
        assert len(f) - head - tail == 0, "iteration 0 has lines the revision drops"
        assert len(s) - head - tail > 0, "no feedback was inserted"

    def test_the_orientation_note_survives_into_the_revision(self, config):
        """Every rung so far has got the row direction wrong; revise_v1 dropped it."""
        first, second = self.prompts(config)
        note = "Row 0 is the top of the board"
        assert note in first
        assert note in second

    def test_the_placement_key_table_survives(self, config):
        first, second = self.prompts(config)
        assert "lines_cleared" in first
        assert "`cells`" in second

    def test_the_measurement_vocabulary_is_present_at_iteration_zero(self, config):
        """Otherwise iteration 1 hands over a vocabulary the model lacked.

        The 4B's iteration-0 trace never mentioned surface shape at all, so this
        was a real confound rather than a hypothetical one.
        """
        first, _ = self.prompts(config)
        for quantity in ("holes", "tallest column", "how uneven"):
            assert quantity in first

    def test_the_declaration_names_quantities_without_defining_them(self, config):
        """Naming what is measured is not the same as explaining what it means."""
        from tetris_bench.loop import MEASUREMENT_DECLARATION

        assert "holes" in MEASUREMENT_DECLARATION
        # the definition every rung has got wrong must not be given away
        assert "covered" not in MEASUREMENT_DECLARATION.lower()
        assert "above" not in MEASUREMENT_DECLARATION.lower()
        assert "for you to work out" in MEASUREMENT_DECLARATION

    def test_the_declaration_can_be_disabled_for_an_ablation(self, config):
        import dataclasses

        bare = dataclasses.replace(config, declare_metrics=False)
        assert "How your function will be judged" not in build_prompt(bare, None)
        assert "How your function will be judged" in build_prompt(config, None)

    def test_one_template_serves_every_iteration(self, config):
        assert config.template == "strategy_v3"


class TestTrainEvalSplit:
    """The curve must be read from sequences the model never informed."""

    @pytest.fixture
    def split_config(self, tmp_path):
        return LoopConfig(
            model="fake",
            train_seeds=(1, 2),
            eval_seeds=(1000, 1001, 1002),
            iterations=2,
            chains=1,
            max_pieces=40,
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "funcs",
        )

    def test_both_splits_are_logged(self, split_config):
        run_loop(FakeClient([HOLES_ONLY, GOOD]), split_config, on_progress=None)
        rows = list(read_records(split_config.log_path))
        train = [r for r in rows if r["split"] == "train"]
        evaluation = [r for r in rows if r["split"] == "eval"]
        assert len(train) == 2 * 2  # 2 train seeds x 2 iterations
        assert len(evaluation) == 3 * 2  # 3 eval seeds x 2 iterations

    def test_the_splits_use_disjoint_seeds(self, split_config):
        run_loop(FakeClient([HOLES_ONLY, GOOD]), split_config, on_progress=None)
        rows = list(read_records(split_config.log_path))
        train = {r["seed"] for r in rows if r["split"] == "train"}
        evaluation = {r["seed"] for r in rows if r["split"] == "eval"}
        assert train == {1, 2}
        assert evaluation == {1000, 1001, 1002}
        assert not train & evaluation

    def test_generation_usage_is_counted_once_per_position(self, split_config):
        """Repeating it per seed would multiply a position's token count."""
        run_loop(FakeClient([HOLES_ONLY, GOOD]), split_config, on_progress=None)
        rows = list(read_records(split_config.log_path))
        for iteration in (0, 1):
            calls = sum(
                r["model_calls"]
                for r in rows
                if r["iteration"] == iteration and r["split"] == "train"
            )
            assert calls == 1, f"iteration {iteration} counted {calls} calls"

    def test_eval_rows_carry_no_generation_usage(self, split_config):
        """Evaluation costs no model calls; it replays a saved function."""
        run_loop(FakeClient([HOLES_ONLY, GOOD]), split_config, on_progress=None)
        rows = list(read_records(split_config.log_path))
        assert all(
            r["model_calls"] == 0 and r["tokens_out"] == 0 for r in rows if r["split"] == "eval"
        )

    def test_a_position_is_only_done_when_every_train_seed_has_a_row(self, split_config):
        """A run killed mid-position must not be skipped with games missing."""
        from tetris_bench.jsonl import append_record
        from tetris_bench.loop import Outcome, _record

        partial = Outcome(source=GOOD, rejected=True, reason="x")
        append_record(
            split_config.log_path,
            _record(Position(0, 0), split_config, partial, ModelUsage(), 1, "train"),
        )
        # only seed 1 of (1, 2) is present
        assert completed_positions(split_config.log_path, "fake", (1, 2)) == set()
        append_record(
            split_config.log_path,
            _record(Position(0, 0), split_config, partial, ModelUsage(), 2, "train"),
        )
        assert completed_positions(split_config.log_path, "fake", (1, 2)) == {(0, 0)}

    def test_feedback_reports_every_training_sequence(self, split_config):
        from tetris_bench.loop import play_on_seeds

        multi = play_on_seeds(GOOD, split_config.train_seeds, split_config)
        text = feedback_text(multi, split_config)
        assert "played 2 games" in text
        assert "mean score" in text
        assert "| 1 |" in text
        assert "| 2 |" in text

    def test_feedback_shows_the_worst_game_s_board(self, split_config):
        """The failure is most legible where the function did worst."""
        from tetris_bench.loop import play_on_seeds

        multi = play_on_seeds(CONSTANT, split_config.train_seeds, split_config)
        text = feedback_text(multi, split_config)
        assert "your worst game" in text
        assert "0123456789" in text

    def test_a_rejected_function_is_not_replayed_per_seed(self, split_config):
        """Validation does not depend on the sequence, so once is enough."""
        from tetris_bench.loop import play_on_seeds

        multi = play_on_seeds(BROKEN, split_config.train_seeds, split_config)
        assert multi.rejected
        assert multi.per_seed == {}

    def test_pooled_diagnostics_sum_across_games(self, split_config):
        from tetris_bench.loop import play_on_seeds

        multi = play_on_seeds(CONSTANT, split_config.train_seeds, split_config)
        pooled = multi.diagnostics
        per_game = [o.diagnostics.moves for o in multi.outcomes]
        assert pooled.moves == sum(per_game)
        assert pooled.is_degenerate
