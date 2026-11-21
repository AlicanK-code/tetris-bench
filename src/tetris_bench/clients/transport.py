"""The thin layer that actually speaks HTTP, and the seam for testing.

:class:`Transport` is a protocol with one method. :class:`OpenAITransport`
implements it against the OpenAI SDK; tests substitute a fake. That seam is the
reason the whole client is testable without a network, an API key or a running
Ollama -- which matters for a benchmark, because the code that records failures
has to be exercised on purpose rather than when a provider happens to be down.

Errors are sorted into two kinds, because that is the only distinction the
retry loop needs: :class:`TransientModelError` is worth trying again (a dropped
connection, a timeout, a rate limit, a 5xx) and
:class:`PermanentModelError` is not (a bad key, a malformed request, a model
that does not exist). Retrying the second kind just burns time and quota.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ModelError(Exception):
    """Base class for anything that went wrong talking to a model."""


class TransientModelError(ModelError):
    """A failure that may succeed on a retry."""


class PermanentModelError(ModelError):
    """A failure that will not succeed on a retry."""


@dataclass(frozen=True)
class RawCompletion:
    """One completion, stripped to what the benchmark records.

    ``reasoning`` is non-standard: Ollama puts a thinking model's chain of
    thought there and leaves the answer in ``content``. It is captured because
    seeing *why* a model revised its scoring function is close to the point of
    the benchmark, and because those tokens are billed whether or not we read
    them. Servers that do not produce it simply leave it empty.
    """

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    reasoning: str = ""


class Transport(Protocol):
    """Sends one chat completion request and returns the result."""

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        timeout: float,
        seed: int | None = None,
        frequency_penalty: float | None = None,
    ) -> RawCompletion:
        """Perform one request, raising a :class:`ModelError` on failure."""
        ...


class OpenAITransport:
    """A :class:`Transport` backed by the OpenAI SDK.

    Works against any OpenAI-compatible endpoint, which is the whole reason the
    project has one client rather than one per provider: Ollama, LM Studio and
    the cloud providers all speak this shape.
    """

    def __init__(self, base_url: str | None, api_key: str) -> None:
        # Imported here rather than at module scope so the rest of the package,
        # and its tests, work without the `llm` extra installed.
        from openai import OpenAI

        # max_retries=0: this client does its own retrying, and leaving the SDK's
        # on would hide attempts from the usage tally and multiply the real count.
        self._client = OpenAI(
            api_key=api_key,
            max_retries=0,
            **({"base_url": base_url} if base_url is not None else {}),
        )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        timeout: float,
        seed: int | None = None,
        frequency_penalty: float | None = None,
    ) -> RawCompletion:
        import openai

        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
        if seed is not None:
            request["seed"] = seed
        if frequency_penalty is not None:
            request["frequency_penalty"] = frequency_penalty

        try:
            completion = self._client.chat.completions.create(**request)
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as e:
            # APITimeoutError subclasses APIConnectionError, so it lands here too.
            raise TransientModelError(f"{type(e).__name__}: {e}") from e
        except openai.APIStatusError as e:
            # Anything else with a status: 5xx is worth retrying, 4xx is not.
            if e.status_code >= 500:
                raise TransientModelError(f"{type(e).__name__}: {e}") from e
            raise PermanentModelError(f"{type(e).__name__}: {e}") from e
        except openai.OpenAIError as e:
            raise PermanentModelError(f"{type(e).__name__}: {e}") from e

        return self._to_raw(completion)

    @staticmethod
    def _to_raw(completion: Any) -> RawCompletion:
        """Pull the text and token counts out of an SDK response.

        Defensive about usage being absent: some OpenAI-compatible servers omit
        it, and a missing tally should cost us a zero rather than a crash
        mid-run.
        """
        if not completion.choices:
            raise PermanentModelError("response contained no choices")

        message = completion.choices[0].message
        usage = getattr(completion, "usage", None)
        return RawCompletion(
            text=message.content or "",
            model=getattr(completion, "model", "") or "",
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            reasoning=getattr(message, "reasoning", "") or "",
        )
