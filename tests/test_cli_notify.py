"""Tests for the CLI's end-of-sweep notification gate.

The gate matters more than the message: a notification that fires when the user
did not ask for one is a surprise POST to a third-party service, so "off unless
the topic is configured" has to be true by test rather than by inspection.
"""

from __future__ import annotations

import argparse

from tetris_bench import cli
from tetris_bench.notify import TOPIC_ENV


def args(**overrides):
    return argparse.Namespace(**{"no_notify": False, **overrides})


class TestWhenNothingIsSent:
    def test_an_unset_topic_is_silence_not_an_error(self, monkeypatch):
        monkeypatch.delenv(TOPIC_ENV, raising=False)
        sent = []
        monkeypatch.setattr("tetris_bench.notify.send", lambda *a, **k: sent.append(a))
        cli._notify_run_ended(args(), title="t", body="b")
        assert sent == []

    def test_no_notify_suppresses_it_even_with_a_topic(self, monkeypatch):
        monkeypatch.setenv(TOPIC_ENV, "some-topic")
        sent = []
        monkeypatch.setattr("tetris_bench.notify.send", lambda *a, **k: sent.append(a))
        cli._notify_run_ended(args(no_notify=True), title="t", body="b")
        assert sent == []

    def test_an_empty_topic_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv(TOPIC_ENV, "")
        sent = []
        monkeypatch.setattr("tetris_bench.notify.send", lambda *a, **k: sent.append(a))
        cli._notify_run_ended(args(), title="t", body="b")
        assert sent == []


class TestWhenSomethingIsSent:
    def test_a_configured_topic_sends_with_the_title_and_body(self, monkeypatch):
        monkeypatch.setenv(TOPIC_ENV, "some-topic")
        captured = {}

        def fake_send(message, **kwargs):
            captured["message"] = message
            captured.update(kwargs)
            return True

        monkeypatch.setattr("tetris_bench.notify.send", fake_send)
        cli._notify_run_ended(args(), title="Sweep finished", body="all good")

        assert captured["message"] == "all good"
        assert captured["title"] == "Sweep finished"

    def test_a_failure_goes_out_at_a_higher_priority(self, monkeypatch):
        monkeypatch.setenv(TOPIC_ENV, "some-topic")
        seen = {}
        monkeypatch.setattr(
            "tetris_bench.notify.send",
            lambda message, **kwargs: seen.update(kwargs) or True,
        )

        cli._notify_run_ended(args(), title="ok", body="b")
        quiet = seen["priority"]
        cli._notify_run_ended(args(), title="bad", body="b", urgent=True)

        assert seen["priority"] > quiet


class TestDurations:
    def test_minutes_only_under_an_hour(self):
        assert cli._hms(90) == "1m"

    def test_hours_and_padded_minutes(self):
        assert cli._hms(3600 * 2 + 60 * 14) == "2h 14m"

    def test_a_long_sweep_reads_naturally(self):
        # The 5x6 sweep took 5.67 hours.
        assert cli._hms(5.67 * 3600) == "5h 40m"
