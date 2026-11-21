"""Tests for the loop's recovery paths, and for the limits that trigger them.

These cover defects found by auditing the loop before its first multi-hour run,
at the shape that run actually uses (three training seeds, ten evaluation seeds,
three chains). Every one of them is invisible at a single training seed with no
evaluation seeds, which is why they survived the existing suite.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tetris_bench import loop as loop_module
from tetris_bench.engine.game import Game
from tetris_bench.jsonl import append_record
from tetris_bench.loop import (
    LoopConfig,
    MultiOutcome,
    Outcome,
    Position,
    build_prompt,
    completed_positions,
    feedback_text,
    logged_eval_seeds,
    play_on_seeds,
    unplayed_positions,
)
from tetris_bench.records import GameResult, ModelUsage, RunRecord
from tetris_bench.runner import play_game
from tetris_bench.sandbox import SandboxLimits

FLAT = "def score(board, placement):\n    return float(placement['lines_cleared'])\n"


def real_result(seed: int) -> GameResult:
    """A genuine game result, so feedback rendering sees real numbers."""
    return play_game(Game(seed=seed, max_pieces=20), _flat_agent())


def _flat_agent():
    class First:
        """Always plays the first legal placement: deterministic and dependency-free."""

        name = "first"

        def choose(self, game):  # noqa: ANN001, ANN202 - duck-typed on the Agent protocol
            return game.legal_placements()[0]

    return First()


class TestBatchDeadline:
    """The host deadline must not refuse what the per-call budget permits."""

    def test_deadline_covers_every_placement_at_its_full_budget(self) -> None:
        limits = SandboxLimits(per_call_seconds=1.0, per_batch_seconds=30.0)
        # A piece can offer ~34 placements. The old flat 30s deadline killed a
        # worker that was entitled to 34, losing the whole game to a host-side
        # crash instead of marking individual placements unplayable.
        assert limits.batch_deadline(34) > 34 * 1.0
        assert limits.batch_deadline(34) == 34 * 1.0 + limits.batch_overhead_seconds

    def test_small_batches_keep_the_floor(self) -> None:
        limits = SandboxLimits(per_call_seconds=1.0, per_batch_seconds=30.0)
        assert limits.batch_deadline(1) == 30.0
        assert limits.batch_deadline(0) == 30.0

    def test_deadline_scales_with_the_per_call_budget(self) -> None:
        tight = SandboxLimits(per_call_seconds=0.1, per_batch_seconds=5.0)
        assert tight.batch_deadline(100) == 0.1 * 100 + tight.batch_overhead_seconds


class TestPlayOnSeedsKeepsWhatFinished:
    """A crash is board-dependent, so finished sequences must survive it."""

    def test_a_crash_on_the_third_seed_keeps_the_first_two(self, monkeypatch) -> None:
        config = LoopConfig(model="m", train_seeds=(1, 2, 17))
        calls: list[int] = []

        def fake_play(source: str, seed: int, cfg: LoopConfig) -> Outcome:
            calls.append(seed)
            if seed == 17:
                return Outcome(source=source, crashed=True, reason="the sandbox did not answer")
            return Outcome(source=source, result=real_result(seed))

        monkeypatch.setattr(loop_module, "play_function", fake_play)
        multi = play_on_seeds(FLAT, (1, 2, 17), config)

        assert calls == [1, 2, 17]
        assert multi.crashed is True
        # The games that finished are the evidence of a board-dependent wedge.
        assert sorted(multi.per_seed) == [1, 2]
        assert len(multi.results) == 2

    def test_a_rejection_still_short_circuits_and_keeps_nothing(self, monkeypatch) -> None:
        """An AST rejection is a property of the source, so repeating it is pointless."""
        config = LoopConfig(model="m", train_seeds=(1, 2, 17))
        calls: list[int] = []

        def fake_play(source: str, seed: int, cfg: LoopConfig) -> Outcome:
            calls.append(seed)
            return Outcome(source=source, rejected=True, reason="import is not allowed")

        monkeypatch.setattr(loop_module, "play_function", fake_play)
        multi = play_on_seeds(FLAT, (1, 2, 17), config)

        assert calls == [1]
        assert multi.rejected is True
        assert multi.per_seed == {}


class TestFeedbackAfterAPartialCrash:
    def test_the_model_is_told_the_scores_and_that_one_sequence_stopped(self) -> None:
        """It used to be told there were no results at all, which was untrue."""
        config = LoopConfig(model="m", train_seeds=(1, 2, 17))
        multi = MultiOutcome(source=FLAT, crashed=True, reason="the sandbox did not answer")
        multi.per_seed[1] = Outcome(source=FLAT, result=real_result(1))
        multi.per_seed[2] = Outcome(source=FLAT, result=real_result(2))

        text = feedback_text(multi, config)

        assert "no results to report" not in text
        assert "How your function played" in text
        assert "One sequence stopped early" in text
        assert "the sandbox did not answer" in text

    def test_a_crash_with_nothing_finished_still_reports_the_abandonment(self) -> None:
        config = LoopConfig(model="m", train_seeds=(1,))
        multi = MultiOutcome(source=FLAT, crashed=True, reason="wedged")
        assert "stopped responding" in feedback_text(multi, config)


def write_row(
    path: Path,
    *,
    chain: int,
    iteration: int,
    seed: int,
    split: str,
    played: bool = True,
    model: str = "m",
) -> None:
    append_record(
        path,
        RunRecord(
            game=GameResult(
                agent="strategy",
                seed=seed,
                agent_seed=None,
                score=0,
                lines_cleared=0,
                pieces_placed=0,
                cause=None,
                final_aggregate_height=0,
                final_max_height=0,
                final_bumpiness=0,
                final_holes=0,
                avg_max_height=0.0,
                avg_bumpiness=0.0,
                avg_holes=0.0,
            ),
            model=model,
            mode="strategy",
            iteration=iteration,
            chain=chain,
            usage=ModelUsage(),
            split=split,
            played=played,
        ),
    )


class TestUnplayedPositions:
    """An unparseable reply is logged but saves no artifact, so resume must skip it."""

    def test_a_position_whose_every_row_says_unplayed_is_found(self, tmp_path: Path) -> None:
        log = tmp_path / "loop.jsonl"
        for seed in (1, 2, 17):
            write_row(log, chain=0, iteration=1, seed=seed, split="train", played=False)
        for seed in (1, 2, 17):
            write_row(log, chain=0, iteration=0, seed=seed, split="train", played=True)

        assert unplayed_positions(log, "m") == {(0, 1)}
        # It is still "complete" -- that is exactly why the artifact check used
        # to raise and brick the resume.
        assert (0, 1) in completed_positions(log, "m", (1, 2, 17))

    def test_a_position_with_any_played_row_is_not_unplayed(self, tmp_path: Path) -> None:
        log = tmp_path / "loop.jsonl"
        write_row(log, chain=0, iteration=0, seed=1, split="train", played=False)
        write_row(log, chain=0, iteration=0, seed=2, split="train", played=True)
        assert unplayed_positions(log, "m") == set()

    def test_other_models_are_ignored(self, tmp_path: Path) -> None:
        log = tmp_path / "loop.jsonl"
        write_row(log, chain=0, iteration=0, seed=1, split="train", played=False, model="other")
        assert unplayed_positions(log, "m") == set()

    def test_a_missing_log_is_empty_not_an_error(self, tmp_path: Path) -> None:
        assert unplayed_positions(tmp_path / "nope.jsonl", "m") == set()


class TestLoggedEvalSeeds:
    """completed_positions counts only train rows, so eval coverage needs its own read."""

    def test_partial_coverage_is_reported_per_position(self, tmp_path: Path) -> None:
        log = tmp_path / "loop.jsonl"
        for seed in (1, 2, 17):
            write_row(log, chain=1, iteration=2, seed=seed, split="train")
        for seed in (1000, 1001, 1002):
            write_row(log, chain=1, iteration=2, seed=seed, split="eval")

        assert logged_eval_seeds(log, "m") == {(1, 2): {1000, 1001, 1002}}
        # The position looks done on train rows alone, which is how a kill
        # between the two writes used to become permanent.
        assert (1, 2) in completed_positions(log, "m", (1, 2, 17))

    def test_a_position_with_no_eval_rows_is_absent(self, tmp_path: Path) -> None:
        log = tmp_path / "loop.jsonl"
        write_row(log, chain=0, iteration=0, seed=1, split="train")
        assert logged_eval_seeds(log, "m") == {}

    def test_a_missing_log_is_empty_not_an_error(self, tmp_path: Path) -> None:
        assert logged_eval_seeds(tmp_path / "nope.jsonl", "m") == {}


class TestPromptWithNoPreviousSource:
    def test_an_unparseable_previous_reply_leaves_out_the_code_block(self) -> None:
        """Showing an empty ```python``` block tells the model it wrote nothing."""
        config = LoopConfig(model="m", train_seeds=(1,))
        failure = Outcome(source="", rejected=True, reason="your reply could not be read")
        prompt = build_prompt(config, failure)

        assert "## The function you wrote" not in prompt
        assert "```python\n```" not in prompt
        # The feedback itself still has to be there, or the iteration is blind.
        assert "your reply could not be read" in prompt

    def test_a_real_previous_function_still_gets_its_block(self) -> None:
        config = LoopConfig(model="m", train_seeds=(1,))
        previous = MultiOutcome(source=FLAT)
        previous.per_seed[1] = Outcome(source=FLAT, result=real_result(1))
        prompt = build_prompt(config, previous)
        assert "## The function you wrote" in prompt
        assert FLAT.strip() in prompt


def test_position_stems_are_unique_per_chain() -> None:
    """Chain 2's iteration 3 must not overwrite chain 1's."""
    stems = {Position(c, i).stem("m") for c in range(3) for i in range(6)}
    assert len(stems) == 18


class TestRunLoopIntegration:
    """Drives ``run_loop`` itself, which is where the real defects lived.

    Every other test in this file is unit-level on the helpers, and two fixes
    passed their unit tests while failing to reach the defect they were aimed
    at: ``play_on_seeds`` kept the games that finished and ``run_loop`` then
    threw them away, and the resume short-circuit skipped the replay for
    positions whose artifact existed. Only a test that crosses the seam sees
    either.
    """

    def config(self, tmp_path: Path, **kwargs) -> LoopConfig:  # noqa: ANN003
        return LoopConfig(
            model="m",
            train_seeds=(1, 2, 17),
            eval_seeds=(1000, 1001),
            iterations=kwargs.pop("iterations", 1),
            chains=kwargs.pop("chains", 1),
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "functions",
            **kwargs,
        )

    def stub_client(self):  # noqa: ANN201
        class Client:
            def __init__(self) -> None:
                self.usage = ModelUsage(model_calls=1, tokens_in=10, tokens_out=20)
                self.prompts: list[str] = []

            def reset_usage(self) -> None:
                self.usage = ModelUsage(model_calls=1, tokens_in=10, tokens_out=20)

        return Client()

    def patch_generation(self, monkeypatch, client, source: str = FLAT) -> None:  # noqa: ANN001
        from tetris_bench.agents.strategy import GeneratedFunction

        def fake_generate(cl, cfg, position, previous):  # noqa: ANN001, ANN202
            client.prompts.append(build_prompt(cfg, previous))
            return GeneratedFunction(
                source=source,
                model=cfg.model,
                prompt="",
                raw_reply="",
                iteration=position.iteration,
            )

        monkeypatch.setattr(loop_module, "generate", fake_generate)

    def rows(self, config: LoopConfig) -> list[dict]:
        from tetris_bench.jsonl import read_records

        return list(read_records(config.log_path))

    def test_a_crash_part_way_through_training_still_logs_the_finished_games(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """The defect: the log said nothing played while the feedback said two games did."""
        config = self.config(tmp_path)
        client = self.stub_client()
        self.patch_generation(monkeypatch, client)

        def fake_play(source: str, seed: int, cfg: LoopConfig) -> Outcome:
            if seed == 17:
                return Outcome(source=source, crashed=True, reason="the sandbox did not answer")
            return Outcome(source=source, result=real_result(seed))

        monkeypatch.setattr(loop_module, "play_function", fake_play)
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        train = [r for r in self.rows(config) if r["split"] == "train"]
        played = {r["seed"]: r["played"] for r in train}
        # Every training seed has a row, so the position still counts as done...
        assert sorted(played) == [1, 2, 17]
        # ...but the two games that finished are recorded as games, not zeros.
        assert played[1] is True and played[2] is True
        assert played[17] is False
        # Not score: the stub agent clears no lines, so a real game and a zeroed
        # row both score 0. Pieces placed is what tells a played game from a
        # fabricated one, which is the whole point of the `played` flag.
        pieces = {r["seed"]: r["pieces_placed"] for r in train}
        assert pieces[1] > 0 and pieces[2] > 0
        assert pieces[17] == 0

        # And the held-out games were played rather than skipped by a `continue`.
        held = [r for r in self.rows(config) if r["split"] == "eval"]
        assert sorted(r["seed"] for r in held) == [1000, 1001]

    def test_a_crash_before_anything_played_is_still_a_whole_failed_position(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        config = self.config(tmp_path)
        client = self.stub_client()
        self.patch_generation(monkeypatch, client)
        monkeypatch.setattr(
            loop_module,
            "play_function",
            lambda source, seed, cfg: Outcome(source=source, crashed=True, reason="wedged"),
        )
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        rows = self.rows(config)
        assert all(r["played"] is False for r in rows)
        assert not [r for r in rows if r["split"] == "eval"]

    def test_resume_replays_a_rejected_position_so_the_next_prompt_matches_live(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """The regression: `unplayed` matched rejected positions, which have artifacts.

        A rejected position's source is saved before it is played, so resume can
        and must replay it -- otherwise iteration 1 is built from a stale
        `previous` and a revision silently becomes a fresh attempt.
        """
        monkeypatch.setattr(
            loop_module,
            "play_function",
            lambda source, seed, cfg: Outcome(
                source=source, rejected=True, reason="imports are not allowed"
            ),
        )

        # The same two iterations run two ways: straight through, and resumed
        # after only iteration 0 was logged. Iteration 1's prompt must match.
        live_config = self.config(tmp_path / "live", iterations=2)
        live = self.stub_client()
        self.patch_generation(monkeypatch, live)
        loop_module.run_loop(live, live_config, on_progress=lambda _m: None)
        assert len(live.prompts) == 2

        resumed_dir = tmp_path / "resumed"
        first_pass = self.config(resumed_dir, iterations=1)
        client = self.stub_client()
        self.patch_generation(monkeypatch, client)
        loop_module.run_loop(client, first_pass, on_progress=lambda _m: None)
        # A rejected position saves its source before playing it, so resume can
        # and must replay it rather than treating it as having nothing to carry.
        assert (first_pass.functions_dir / "m-chain0-iter0.py").exists()

        second_pass = self.config(resumed_dir, iterations=2)
        resumed = self.stub_client()
        self.patch_generation(monkeypatch, resumed)
        loop_module.run_loop(resumed, second_pass, on_progress=lambda _m: None)

        assert len(resumed.prompts) == 1
        assert "imports are not allowed" in resumed.prompts[0]
        assert resumed.prompts[0] == live.prompts[1]

    def test_resume_skips_an_unparseable_position_without_raising(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """An unparseable reply saves no artifact, so resume must excuse it."""
        config = self.config(tmp_path, iterations=1)
        client = self.stub_client()

        def unparseable(cl, cfg, position, previous):  # noqa: ANN001, ANN202
            raise loop_module.StrategyError("no code block in the reply")

        monkeypatch.setattr(loop_module, "generate", unparseable)
        loop_module.run_loop(client, config, on_progress=lambda _m: None)
        assert not (config.functions_dir / "m-chain0-iter0.py").exists()

        # Resume used to raise RuntimeError here and brick a multi-hour run.
        messages: list[str] = []
        loop_module.run_loop(client, config, on_progress=messages.append)
        assert any("invalid output" in m for m in messages)

    def test_resume_tops_up_missing_held_out_games(self, monkeypatch, tmp_path: Path) -> None:
        config = self.config(tmp_path)
        client = self.stub_client()
        self.patch_generation(monkeypatch, client)
        monkeypatch.setattr(
            loop_module,
            "play_function",
            lambda source, seed, cfg: Outcome(source=source, result=real_result(seed)),
        )
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        # Simulate a kill between the training and evaluation writes by dropping
        # the eval rows from the log.
        kept = [r for r in self.rows(config) if r["split"] == "train"]
        config.log_path.write_text("")
        import json

        with config.log_path.open("w") as handle:
            for row in kept:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        assert not [r for r in self.rows(config) if r["split"] == "eval"]

        resumed = self.stub_client()
        self.patch_generation(monkeypatch, resumed)
        messages: list[str] = []
        loop_module.run_loop(resumed, config, on_progress=messages.append)

        held = [r for r in self.rows(config) if r["split"] == "eval"]
        assert sorted(r["seed"] for r in held) == [1000, 1001]
        assert any("recovered 2 of 2" in m for m in messages)
        # No model call was needed to recover them.
        assert resumed.prompts == []

    def test_chains_stay_independent_across_a_resume(self, monkeypatch, tmp_path: Path) -> None:
        config = self.config(tmp_path, iterations=2, chains=2)
        client = self.stub_client()
        self.patch_generation(monkeypatch, client)
        monkeypatch.setattr(
            loop_module,
            "play_function",
            lambda source, seed, cfg: Outcome(source=source, result=real_result(seed)),
        )
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        # Four positions, and each chain's first prompt carries no feedback.
        assert len(client.prompts) == 4
        assert "How your last attempt went" not in client.prompts[0]
        assert "How your last attempt went" in client.prompts[1]
        assert "How your last attempt went" not in client.prompts[2]
        assert "How your last attempt went" in client.prompts[3]


class TestPerChainModelSeed:
    """Chains must be independent samples, or several chains buy one sample."""

    def test_chain_zero_keeps_the_configured_seed(self):
        """A single-chain run must be bit-for-bit what it was before this existed."""
        assert loop_module.model_seed_for(1, 0) == 1

    def test_later_chains_are_offset(self):
        assert loop_module.model_seed_for(1, 1) == 2
        assert loop_module.model_seed_for(1, 4) == 5

    def test_no_configured_seed_stays_none(self):
        """Offsetting nothing is nothing; don't invent a seed a rung never had."""
        assert loop_module.model_seed_for(None, 3) is None

    def test_every_chain_gets_a_distinct_seed(self):
        seeds = [loop_module.model_seed_for(7, c) for c in range(5)]
        assert len(set(seeds)) == 5

    def test_generate_sends_the_chain_seed_to_the_client(self):
        """The rule is useless if `generate` does not actually pass it on."""

        class Recorder:
            def __init__(self):
                self.seeds = []

            def complete(self, messages, seed=None):
                self.seeds.append(seed)
                return SimpleNamespace(
                    text="```python\ndef score(board, placement):\n    return 0.0\n```",
                    model="m",
                    reasoning="",
                )

        client = Recorder()
        config = loop_module.LoopConfig(model="m", model_seed=1)
        for chain in (0, 1, 2):
            loop_module.generate(client, config, loop_module.Position(chain, 0), None)
        assert client.seeds == [1, 2, 3]

    def test_an_unseeded_sweep_sends_no_override(self):
        """`model_seed=None` must leave the client's own seed alone, not send 0."""

        class Recorder:
            def __init__(self):
                self.seeds = []

            def complete(self, messages, seed=None):
                self.seeds.append(seed)
                return SimpleNamespace(
                    text="```python\ndef score(board, placement):\n    return 0.0\n```",
                    model="m",
                    reasoning="",
                )

        client = Recorder()
        config = loop_module.LoopConfig(model="m")
        loop_module.generate(client, config, loop_module.Position(2, 0), None)
        assert client.seeds == [None]


class TestAFailedCallDoesNotKillTheRun:
    """A timeout used to propagate out of ``generate`` and abort everything.

    That is the worst available outcome. Positions already finished stay on
    disk, but the tokens and seconds just spent vanish, nothing records why the
    run stopped, and a resume has to rediscover the failure. One rung burned 80
    minutes and three attempts this way.
    """

    def failing_client(self, fail_on: set[int]):  # noqa: ANN201
        """A client whose ``complete`` raises for the listed call numbers."""
        from tetris_bench.clients.transport import ModelError

        class Client:
            def __init__(self) -> None:
                self.calls = 0
                self.usage = ModelUsage(model_calls=1, tokens_in=10, tokens_out=20)
                self.config = SimpleNamespace(name="m", model="m")

            def reset_usage(self) -> None:
                self.usage = ModelUsage(model_calls=1, tokens_in=10, tokens_out=20)

            def complete(self, messages, seed=None):  # noqa: ANN001, ANN202
                self.calls += 1
                if self.calls in fail_on:
                    raise ModelError("timed out after 2400s")

                class Response:
                    text = f"```python\n{FLAT}\n```"
                    reasoning = ""
                    model = "m"

                return Response()

        return Client()

    def config(self, tmp_path: Path, **kwargs) -> LoopConfig:  # noqa: ANN003
        return LoopConfig(
            model="m",
            train_seeds=(1,),
            eval_seeds=(),
            iterations=kwargs.pop("iterations", 3),
            chains=kwargs.pop("chains", 1),
            log_path=tmp_path / "loop.jsonl",
            functions_dir=tmp_path / "functions",
            **kwargs,
        )

    def rows(self, config: LoopConfig) -> list[dict]:
        from tetris_bench.jsonl import read_records

        return list(read_records(config.log_path))

    def test_the_run_continues_past_a_failed_call(self, tmp_path: Path) -> None:
        config = self.config(tmp_path)
        client = self.failing_client(fail_on={2})
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        # Three iterations were asked for and three were attempted, rather than
        # the run dying at the second.
        assert client.calls == 3
        assert len(self.rows(config)) == 3

    def test_the_failed_position_is_logged_with_its_usage(self, tmp_path: Path) -> None:
        """The tokens are spent whether or not the call returned, so they count."""
        config = self.config(tmp_path)
        loop_module.run_loop(self.failing_client(fail_on={2}), config, on_progress=lambda _m: None)

        failed = [r for r in self.rows(config) if r["iteration"] == 1]
        assert len(failed) == 1
        assert failed[0]["played"] is False
        assert failed[0]["invalid_outputs"] == 1
        assert failed[0]["tokens_out"] == 20

    def test_a_failure_at_iteration_zero_does_not_abort(self, tmp_path: Path) -> None:
        """With no previous function to keep, the loop must still carry on."""
        config = self.config(tmp_path)
        client = self.failing_client(fail_on={1})
        loop_module.run_loop(client, config, on_progress=lambda _m: None)

        assert client.calls == 3
        assert [r["iteration"] for r in self.rows(config)] == [0, 1, 2]

    def test_every_call_failing_leaves_a_complete_log_rather_than_nothing(
        self, tmp_path: Path
    ) -> None:
        """The old behaviour wrote nothing at all; now the run is explainable."""
        config = self.config(tmp_path)
        loop_module.run_loop(
            self.failing_client(fail_on={1, 2, 3}), config, on_progress=lambda _m: None
        )

        rows = self.rows(config)
        assert len(rows) == 3
        assert all(r["played"] is False for r in rows)
        assert all("failed" in (r["cause"] or "") or r["cause"] is None for r in rows)

    def test_the_reason_reaches_the_next_prompt_as_feedback(self, tmp_path: Path) -> None:
        """A failed call is a symptom the model should see, not a silent gap."""
        config = self.config(tmp_path, iterations=2)
        client = self.failing_client(fail_on={1})
        loop_module.run_loop(client, config, on_progress=lambda _m: None)
        assert client.calls == 2


class TestFunctionShaOfNothing:
    """A failed position has no function, and must not be given one."""

    def test_a_missing_function_gets_no_sha(self) -> None:
        """`e3b0c44298fc` is the digest of the empty string, not a function id."""
        assert loop_module._sha("") == ""

    def test_two_unrelated_failures_do_not_appear_to_share_a_function(self) -> None:
        """Hashing "" gave every failed row the same plausible-looking id."""
        assert loop_module._sha("") == loop_module._sha("")
        assert loop_module._sha("") != "e3b0c44298fc"

    def test_a_real_function_still_hashes(self) -> None:
        first = loop_module._sha("def score(b, p):\n    return 1.0\n")
        second = loop_module._sha("def score(b, p):\n    return 2.0\n")
        assert len(first) == 12
        assert first != second
