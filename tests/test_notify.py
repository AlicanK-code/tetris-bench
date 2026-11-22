"""Tests for the ntfy notifier. Nothing here touches the network."""

from __future__ import annotations

import urllib.error

import pytest

from tetris_bench import notify


class TestResolvingTheTopic:
    def test_an_explicit_topic_wins(self):
        assert notify.resolve_topic("given", {"NTFY_TOPIC": "from-env"}) == "given"

    def test_otherwise_it_comes_from_the_environment(self):
        assert notify.resolve_topic(None, {"NTFY_TOPIC": "from-env"}) == "from-env"

    def test_surrounding_whitespace_is_ignored(self):
        assert notify.resolve_topic(None, {"NTFY_TOPIC": "  spaced  "}) == "spaced"

    def test_an_unset_topic_raises_rather_than_defaulting(self):
        # A default topic name would publish to a channel a stranger may already
        # be subscribed to, so there must not be one.
        with pytest.raises(notify.NotifyError, match="NTFY_TOPIC"):
            notify.resolve_topic(None, {})

    def test_an_empty_topic_counts_as_unset(self):
        with pytest.raises(notify.NotifyError):
            notify.resolve_topic(None, {"NTFY_TOPIC": "   "})


class TestSending:
    def test_it_posts_the_message_to_the_topic_url(self, monkeypatch):
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["body"] = request.data
            seen["headers"] = request.headers
            seen["method"] = request.get_method()
            return _Reply()

        monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
        assert notify.send("hello", title="t", tags=["a", "b"], topic="my-topic") is True

        assert seen["url"] == "https://ntfy.sh/my-topic"
        assert seen["body"] == b"hello"
        assert seen["method"] == "POST"
        assert seen["headers"]["Title"] == "t"
        assert seen["headers"]["Tags"] == "a,b"

    def test_a_trailing_slash_on_the_server_does_not_double_up(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            notify.urllib.request,
            "urlopen",
            lambda request, timeout=None: (seen.update(url=request.full_url), _Reply())[1],
        )
        notify.send("x", topic="t", server="https://example.test/")
        assert seen["url"] == "https://example.test/t"

    def test_a_network_failure_is_reported_but_not_raised(self, monkeypatch):
        # The run this reports on has already written its results to disk, so a
        # dropped notification must not become an exception that ends it.
        def boom(request, timeout=None):
            raise urllib.error.URLError("no route to host")

        monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
        assert notify.send("hello", topic="t") is False

    def test_a_missing_topic_still_raises(self, monkeypatch):
        monkeypatch.delenv(notify.TOPIC_ENV, raising=False)
        with pytest.raises(notify.NotifyError):
            notify.send("hello")


class _Reply:
    """The minimum of a urlopen context manager that `json.load` accepts."""

    def read(self):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
