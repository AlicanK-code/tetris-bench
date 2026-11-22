"""Tests for `summarise_run`, the text a finished sweep notifies with."""

from __future__ import annotations

import json

import pytest

from tetris_bench.loop import summarise_run


def write_log(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def row(*, chain, iteration, split, seed, score, model="m", tokens_out=0, failed=0):
    return {
        "model": model,
        "chain": chain,
        "iteration": iteration,
        "split": split,
        "seed": seed,
        "score": score,
        "tokens_out": tokens_out,
        "failed_calls": failed,
    }


@pytest.fixture
def log(tmp_path):
    return tmp_path / "loop.jsonl"


class TestWhenThereIsNothingToSummarise:
    def test_an_empty_log_says_so_rather_than_raising(self, log):
        write_log(log, [])
        assert "no records" in summarise_run(log, "m")

    def test_another_models_rows_do_not_count(self, log):
        write_log(log, [row(chain=0, iteration=0, split="eval", seed=1000, score=5, model="other")])
        assert "no records" in summarise_run(log, "m")


class TestTheHeldOutCurve:
    def test_it_reports_the_first_and_last_iteration(self, log):
        write_log(
            log,
            [
                row(chain=0, iteration=0, split="eval", seed=1000, score=100),
                row(chain=0, iteration=1, split="eval", seed=1000, score=900),
            ],
        )
        text = summarise_run(log, "m")
        assert "it0 100" in text
        assert "it1 900" in text

    def test_the_median_across_chains_is_the_default(self, log):
        # Three chains at one iteration: 0, 100, 5000. Median 100, mean 1700.
        write_log(
            log,
            [
                row(chain=0, iteration=0, split="eval", seed=1000, score=0),
                row(chain=1, iteration=0, split="eval", seed=1000, score=100),
                row(chain=2, iteration=0, split="eval", seed=1000, score=5000),
            ],
        )
        assert "median it0 100" in summarise_run(log, "m")
        assert "mean it0 1,700" in summarise_run(log, "m", statistic="mean")

    def test_an_unknown_statistic_is_refused(self, log):
        write_log(log, [row(chain=0, iteration=0, split="eval", seed=1000, score=1)])
        with pytest.raises(ValueError, match="median"):
            summarise_run(log, "m", statistic="mode")

    def test_the_spread_between_chains_is_reported(self, log):
        write_log(
            log,
            [
                row(chain=0, iteration=0, split="eval", seed=1000, score=10),
                row(chain=1, iteration=0, split="eval", seed=1000, score=9600),
            ],
        )
        # The point of printing it: 9,590 dwarfs any movement, so a reader can
        # see at a glance that a rise between iterations would not be news.
        assert "widest spread between chains 9,590" in summarise_run(log, "m")

    def test_one_chain_has_no_spread_to_report(self, log):
        write_log(log, [row(chain=0, iteration=0, split="eval", seed=1000, score=10)])
        assert "spread" not in summarise_run(log, "m")


class TestCountingWork:
    def test_generations_are_positions_not_rows(self, log):
        # Two positions, each with several games, must not count as four.
        write_log(
            log,
            [
                row(chain=0, iteration=0, split="train", seed=1, score=1),
                row(chain=0, iteration=0, split="eval", seed=1000, score=1),
                row(chain=0, iteration=1, split="train", seed=1, score=1),
                row(chain=0, iteration=1, split="eval", seed=1000, score=1),
            ],
        )
        assert "2 generations" in summarise_run(log, "m")

    def test_tokens_are_not_multiplied_by_the_training_seeds(self, log):
        # Usage is repeated on every row of a position, so a naive sum would
        # report three times the tokens actually generated.
        write_log(
            log,
            [
                row(chain=0, iteration=0, split="train", seed=1, score=1, tokens_out=500),
                row(chain=0, iteration=0, split="train", seed=2, score=1, tokens_out=500),
                row(chain=0, iteration=0, split="train", seed=17, score=1, tokens_out=500),
            ],
        )
        assert "500 tokens out" in summarise_run(log, "m")

    def test_failed_calls_are_surfaced(self, log):
        write_log(
            log,
            [row(chain=0, iteration=0, split="train", seed=1, score=0, failed=1)],
        )
        assert "1 failed model call(s)" in summarise_run(log, "m")

    def test_a_clean_run_does_not_mention_failures(self, log):
        write_log(log, [row(chain=0, iteration=0, split="train", seed=1, score=1)])
        assert "failed" not in summarise_run(log, "m")
