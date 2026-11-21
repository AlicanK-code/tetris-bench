"""Tests for the HTTP transport and its error classification."""

from types import SimpleNamespace

import httpx2
import openai
import pytest

from tetris_bench.clients.transport import (
    OpenAITransport,
    PermanentModelError,
    TransientModelError,
)

REQUEST = httpx2.Request("POST", "http://localhost:11434/v1/chat/completions")


def completion(text="hi", model="m", tokens_in=10, tokens_out=5, *, usage=True, choices=True):
    """A stand-in for an SDK response, shaped like the bits we read."""
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))] if choices else [],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
        if usage
        else None,
    )


def transport_raising(error: Exception) -> OpenAITransport:
    """A transport whose underlying SDK call always raises ``error``."""
    transport = OpenAITransport(base_url="http://localhost:11434/v1", api_key="x")

    def create(**_kwargs):
        raise error

    transport._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return transport


def transport_returning(result) -> OpenAITransport:
    transport = OpenAITransport(base_url="http://localhost:11434/v1", api_key="x")
    transport._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: result))
    )
    return transport


def call(transport: OpenAITransport):
    return transport.chat(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=None,
        timeout=5.0,
    )


class TestRequestAssembly:
    """What actually reaches the SDK, since an ignored field fixes nothing."""

    def captured(self, **extra):
        seen = {}

        def create(**kwargs):
            seen.update(kwargs)
            return completion()

        transport = OpenAITransport(base_url="http://x/v1", api_key="x")
        transport._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        transport.chat(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            max_tokens=None,
            timeout=5.0,
            **extra,
        )
        return seen

    def test_frequency_penalty_is_omitted_when_unset(self):
        """An explicit 0.0 and "not set" are different requests; don't conflate them."""
        assert "frequency_penalty" not in self.captured()

    def test_frequency_penalty_is_sent_when_set(self):
        assert self.captured(frequency_penalty=0.5)["frequency_penalty"] == 0.5

    def test_a_zero_penalty_is_still_sent(self):
        assert self.captured(frequency_penalty=0.0)["frequency_penalty"] == 0.0


class TestToRaw:
    def test_extracts_text_and_tokens(self):
        raw = call(transport_returning(completion()))
        assert raw.text == "hi"
        assert raw.tokens_in == 10
        assert raw.tokens_out == 5

    def test_missing_usage_counts_as_zero_rather_than_crashing(self):
        """Some OpenAI-compatible servers omit usage; that must not end a run."""
        raw = call(transport_returning(completion(usage=False)))
        assert raw.tokens_in == 0
        assert raw.tokens_out == 0

    def test_null_content_becomes_an_empty_string(self):
        raw = call(transport_returning(completion(text=None)))
        assert raw.text == ""

    def test_no_choices_is_a_permanent_failure(self):
        with pytest.raises(PermanentModelError, match="no choices"):
            call(transport_returning(completion(choices=False)))


class TestErrorClassification:
    @pytest.mark.parametrize(
        "error",
        [
            openai.APIConnectionError(request=REQUEST),
            openai.APITimeoutError(request=REQUEST),
            openai.RateLimitError(
                "slow down", response=httpx2.Response(429, request=REQUEST), body=None
            ),
            openai.InternalServerError(
                "boom", response=httpx2.Response(500, request=REQUEST), body=None
            ),
        ],
    )
    def test_transport_failures_and_rate_limits_are_transient(self, error):
        with pytest.raises(TransientModelError):
            call(transport_raising(error))

    @pytest.mark.parametrize(
        "error",
        [
            openai.AuthenticationError(
                "bad key", response=httpx2.Response(401, request=REQUEST), body=None
            ),
            openai.BadRequestError(
                "bad", response=httpx2.Response(400, request=REQUEST), body=None
            ),
            openai.NotFoundError(
                "no model", response=httpx2.Response(404, request=REQUEST), body=None
            ),
        ],
    )
    def test_client_errors_are_permanent(self, error):
        """Retrying a bad key or a missing model just burns time and quota."""
        with pytest.raises(PermanentModelError):
            call(transport_raising(error))

    def test_unmapped_5xx_is_transient(self):
        error = openai.APIStatusError(
            "gateway", response=httpx2.Response(503, request=REQUEST), body=None
        )
        with pytest.raises(TransientModelError):
            call(transport_raising(error))

    def test_unmapped_4xx_is_permanent(self):
        error = openai.APIStatusError(
            "teapot", response=httpx2.Response(418, request=REQUEST), body=None
        )
        with pytest.raises(PermanentModelError):
            call(transport_raising(error))

    def test_other_sdk_errors_are_permanent(self):
        with pytest.raises(PermanentModelError):
            call(transport_raising(openai.OpenAIError("something else")))

    def test_the_error_message_names_the_original_type(self):
        with pytest.raises(TransientModelError, match="APIConnectionError"):
            call(transport_raising(openai.APIConnectionError(request=REQUEST)))


def test_sdk_retries_are_disabled_so_our_tally_stays_honest():
    """The SDK retrying behind our back would hide attempts from the usage count."""
    transport = OpenAITransport(base_url="http://localhost:11434/v1", api_key="x")
    assert transport._client.max_retries == 0
