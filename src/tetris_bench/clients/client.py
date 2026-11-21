"""One client for every model, with retries and a usage tally.

The provider is configuration: a base URL, a model id and a key environment
variable. Local runtimes and cloud APIs all speak the OpenAI chat shape, so
there is one code path for both, and swapping a 30B local model for a frontier
API model is a config edit.

Transient failures are retried here with exponential backoff, so callers only
have to handle *semantic* failures -- output that will not parse, a scoring
function that will not compile. Retries are tallied apart from calls:
``model_calls`` counts logical calls so cost-per-call stays meaningful, while
``retries`` records the flakiness separately. Latency is wall-clock and so
includes time spent retrying, because that is what a run actually costs in time.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from tetris_bench.clients.config import ModelConfig
from tetris_bench.clients.providers import LOCAL_PLACEHOLDER_KEY
from tetris_bench.clients.transport import (
    ModelError,
    OpenAITransport,
    PermanentModelError,
    RawCompletion,
    TransientModelError,
    Transport,
)
from tetris_bench.records import ModelUsage

BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 30.0


@dataclass(frozen=True)
class ChatResponse:
    """One logical call's result, including what it cost."""

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_seconds: float
    retries: int
    estimated_cost_usd: float
    reasoning: str = ""


def resolve_api_key(config: ModelConfig, environ: dict[str, str] | None = None) -> str:
    """Read the configured key from the environment.

    Providers that need no credential get a placeholder, because the SDK rejects
    an empty key even when the server ignores it. A provider that *does* need one
    fails here, at setup, rather than on the first call of a long run.
    """
    env = os.environ if environ is None else environ
    spec = config.provider_spec
    if not spec.requires_key:
        return LOCAL_PLACEHOLDER_KEY

    assert spec.api_key_env is not None  # requires_key guarantees this
    key = env.get(spec.api_key_env, "")
    if not key:
        raise PermanentModelError(
            f"model {config.name!r} needs {spec.api_key_env} set in the environment"
        )
    return key


class ModelClient:
    """Calls one configured model, tracking tokens, latency and cost."""

    def __init__(
        self,
        config: ModelConfig,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._sleep = sleep
        self._clock = clock
        self._usage = ModelUsage()
        if transport is None:
            spec = config.provider_spec
            transport = OpenAITransport(base_url=spec.base_url, api_key=resolve_api_key(config))
        self._transport = transport

    @property
    def usage(self) -> ModelUsage:
        """Totals since construction, or since :meth:`reset_usage`."""
        return self._usage

    def reset_usage(self) -> None:
        """Zero the tally, so one game's usage can be recorded on its own."""
        self._usage = ModelUsage()

    def complete(self, messages: list[dict[str, str]], seed: int | None = None) -> ChatResponse:
        """Send one chat request, retrying transient failures.

        Raises the last :class:`ModelError` if every attempt fails. The usage
        tally is still updated in that case: a run's cost includes the calls that
        did not work.

        ``seed`` overrides the configured one for this call, so that several
        samples of a model's generation noise can be drawn through one client.

        It only does anything **above temperature 0**. Greedy decoding takes the
        argmax at every step and never draws from the RNG, so there is no random
        number for a seed to index: measured, three seeds at temperature 0 give
        one byte-identical generation, and at temperature 1.0 give three
        different ones. A sweep that varies this while ``temperature`` is 0 pays
        N times for one sample -- which is what the first five-chain run did.
        See ``docs/findings/seed-is-inert-at-temperature-zero.md``.
        """
        started = self._clock()
        attempts = self.config.max_retries + 1
        retries = 0
        last_error: ModelError | None = None

        for attempt in range(attempts):
            try:
                raw = self._transport.chat(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.timeout_seconds,
                    seed=self.config.seed if seed is None else seed,
                    frequency_penalty=self.config.frequency_penalty,
                )
            except PermanentModelError:
                # No point trying again; record the attempt and surface it.
                self._record_failure(self._clock() - started, retries)
                raise
            except TransientModelError as error:
                last_error = error
                if attempt == attempts - 1:
                    break
                retries += 1
                self._sleep(min(BACKOFF_BASE_SECONDS * 2**attempt, BACKOFF_CAP_SECONDS))
                continue

            return self._record_success(raw, self._clock() - started, retries)

        self._record_failure(self._clock() - started, retries)
        assert last_error is not None  # the loop only breaks after a transient error
        raise last_error

    def _record_success(self, raw: RawCompletion, latency: float, retries: int) -> ChatResponse:
        cost = self.config.pricing.cost(raw.tokens_in, raw.tokens_out)
        self._usage = replace(
            self._usage,
            model_calls=self._usage.model_calls + 1,
            tokens_in=self._usage.tokens_in + raw.tokens_in,
            tokens_out=self._usage.tokens_out + raw.tokens_out,
            latency_seconds=self._usage.latency_seconds + latency,
            estimated_cost_usd=self._usage.estimated_cost_usd + cost,
            retries=self._usage.retries + retries,
        )
        return ChatResponse(
            text=raw.text,
            model=raw.model or self.config.model,
            tokens_in=raw.tokens_in,
            tokens_out=raw.tokens_out,
            latency_seconds=latency,
            retries=retries,
            estimated_cost_usd=cost,
            reasoning=raw.reasoning,
        )

    def _record_failure(self, latency: float, retries: int) -> None:
        """A failed call still consumed time, and still counts as a call."""
        self._usage = replace(
            self._usage,
            model_calls=self._usage.model_calls + 1,
            latency_seconds=self._usage.latency_seconds + latency,
            retries=self._usage.retries + retries,
            failed_calls=self._usage.failed_calls + 1,
        )
