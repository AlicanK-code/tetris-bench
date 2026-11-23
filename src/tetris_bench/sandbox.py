"""Running model-written scoring functions safely.

Two layers, because neither alone is enough.

:func:`validate_source` is a static AST allowlist. It rejects imports, private
and dunder attribute access, and the builtins that reach outside the process --
before anything executes. The point is not that a subprocess could not contain
those anyway; it is that a rejected function fails instantly with a readable
reason, instead of spending a timeout and leaving you guessing.

:class:`ScoringSandbox` is the containment layer. It runs
:mod:`tetris_bench.sandbox_worker` as a separate interpreter under ``-I``, with
no project module importable, a small allowlist of builtins, and ``SIGALRM``
bounding every call.

**One worker per game, batched per piece.** A game is up to 2000 pieces with
roughly 34 placements each, so scoring one placement per process would mean
68,000 spawns and, at about 30ms each, over half an hour per game spent purely
on process creation. Instead the worker starts once, and each piece's whole
placement list crosses the pipe in one round trip.

**The function sees plain data only.** Boards arrive as tuples of tuples of
bool and placements as plain dicts, so nothing of this project crosses into the
sandbox -- not a class, not a module, not a method. The board it receives is the
board the move *would produce*, after the piece locks and any rows clear, since
scoring the current board would rate every candidate identically.
"""

from __future__ import annotations

import ast
import json
import selectors
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from tetris_bench.engine.board import Board
from tetris_bench.engine.placements import Placement, apply_placement

WORKER_PATH = Path(__file__).with_name("sandbox_worker.py")
FUNCTION_NAME = "score"
UNPLAYABLE = float("-inf")

#: Builtins that reach outside the process, inspect it, or execute more code.
FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "hasattr",
        "help",
        "id",
        "input",
        "locals",
        "memoryview",
        "object",
        "open",
        "quit",
        "setattr",
        "super",
        "type",
        "vars",
    }
)


class SandboxError(Exception):
    """Base class for sandbox failures."""


class SandboxValidationError(SandboxError):
    """The source was rejected before it ran."""


class SandboxCrashed(SandboxError):
    """The worker died or stopped answering."""


class SandboxGameDeadline(SandboxCrashed):
    """The game exceeded its whole-game time budget.

    A subclass of :class:`SandboxCrashed` on purpose. Every caller already
    handles that as "this game is over, record a failure, keep the sweep
    running", which is exactly the right response here too -- so the deadline
    cannot crash a run through a handler someone forgot to add. The distinct
    type is for telling the two apart afterwards: a crash means the worker
    stopped answering, this means the function was simply too slow.
    """


@dataclass(frozen=True)
class SandboxLimits:
    """Time budgets for model-written code.

    ``per_call_seconds`` bounds one placement, enforced inside the worker by
    ``SIGALRM``. ``per_batch_seconds`` is the **floor** on the host's own
    deadline for a whole piece's worth of placements, which catches a worker
    that has stopped answering altogether rather than merely looping in one
    call.

    A floor rather than a fixed value, because the two budgets were previously
    inconsistent: a piece can offer ~34 placements, so ``per_call_seconds`` of
    1.0 permits the worker up to 34 seconds that a flat 30-second host deadline
    then refused. A function merely *slow* on every placement therefore lost its
    whole game to a host-side crash, when the design is that an individual
    placement comes back as unplayable and the game continues. See
    :meth:`batch_deadline`.

    ``per_game_seconds`` closes what those two budgets leave open. Bounding the
    call and the piece does not bound the game: a function that merely spends its
    full second on every placement, never looping, can run
    ``2000 pieces x 34 placements x 1s`` -- about **19 hours** -- entirely within
    the rules. Nothing stopped it, and an unattended sweep would simply appear to
    hang.
    """

    per_call_seconds: float = 1.0
    per_batch_seconds: float = 30.0
    load_seconds: float = 10.0
    #: Slack for process round-trip and JSON encoding on top of the per-call
    #: budgets. Generous because overshooting the deadline costs a whole game.
    batch_overhead_seconds: float = 10.0
    #: Wall-clock budget for one whole game, or ``None`` for no limit.
    #:
    #: 300s is roughly a thousand times a real game. Measured on the size
    #: ladder, 728 sandboxed games took about 92 seconds between them -- ~0.13s
    #: each -- because a scoring function is tens of lines of pure Python over a
    #: 200-cell board, which is microseconds of work per placement. A function
    #: needing minutes is pathological, not merely slow, so this is set to catch
    #: pathology without being a budget any plausible function competes with.
    #:
    #: ``None`` exists for deliberately long replays (a 50,000-piece budget, for
    #: instance), where a long game is the point rather than a symptom.
    per_game_seconds: float | None = 300.0

    def batch_deadline(self, items: int) -> float:
        """Host deadline for a batch of ``items`` placements.

        At least what the per-call budget permits the worker to spend on every
        placement, plus overhead -- otherwise the host kills a worker that is
        behaving exactly as allowed.
        """
        return max(
            self.per_batch_seconds,
            self.per_call_seconds * items + self.batch_overhead_seconds,
        )


#: Attribute names that are not dunders but still reach the type hierarchy.
#: ``int.mro()`` returns ``[int, object]``, and the allowlist has always
#: contained type constructors (`int`, `list`, `dict`, `set`, `tuple`), so `mro`
#: is the one non-dunder step from a value to `object`. The next step --
#: `__subclasses__` -- is already refused as a dunder, so this is defence in
#: depth rather than a hole being closed. No scoring function needs it.
BLOCKED_ATTRIBUTES = frozenset({"mro"})


class _Validator(ast.NodeVisitor):
    """Walks the tree and collects every reason to refuse it."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        names = ", ".join(alias.name for alias in node.names)
        self.problems.append(
            f"line {node.lineno}: imports are not allowed (found {names}); "
            f"'math' is already available without importing it"
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.problems.append(
            f"line {node.lineno}: imports are not allowed (found {node.module}); "
            f"'math' is already available without importing it"
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.problems.append(
                f"line {node.lineno}: attribute {node.attr!r} is not allowed "
                f"(private and dunder attributes are blocked)"
            )
        elif node.attr in BLOCKED_ATTRIBUTES:
            self.problems.append(
                f"line {node.lineno}: attribute {node.attr!r} is not allowed "
                f"(it reaches the type hierarchy)"
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            self.problems.append(f"line {node.lineno}: name {node.id!r} is not allowed")
        elif node.id in FORBIDDEN_NAMES:
            self.problems.append(f"line {node.lineno}: {node.id!r} is not available")
        self.generic_visit(node)

    def _reject_async(self, node: ast.AST, what: str) -> None:
        self.problems.append(f"line {getattr(node, 'lineno', '?')}: {what} is not allowed")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._reject_async(node, "async def")

    def visit_Await(self, node: ast.Await) -> None:
        self._reject_async(node, "await")

    def visit_Yield(self, node: ast.Yield) -> None:
        self._reject_async(node, "yield")

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self._reject_async(node, "yield from")


def validate_source(source: str) -> None:
    """Refuse model-written source that must not be executed.

    Raises :class:`SandboxValidationError` listing every problem found, so a
    model revising its function gets the whole story in one go rather than one
    complaint per attempt.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise SandboxValidationError(f"syntax error on line {error.lineno}: {error.msg}") from error

    validator = _Validator()
    validator.visit(tree)

    definition = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
        ),
        None,
    )
    if definition is None:
        validator.problems.append(f"no function called {FUNCTION_NAME!r} is defined")
    else:
        arguments = definition.args
        count = len(arguments.posonlyargs) + len(arguments.args)
        if count != 2:
            validator.problems.append(
                f"{FUNCTION_NAME}() takes {count} arguments, expected 2 (board, placement)"
            )

    if validator.problems:
        raise SandboxValidationError("; ".join(validator.problems))


def build_items(board: Board, placements: Sequence[Placement]) -> list[dict]:
    """Turn candidate placements into plain data for the sandbox.

    Each item carries the board the placement *would produce* and how many rows
    it cleared, so the function scores consequences rather than the board as it
    stands -- which would be identical for every candidate.
    """
    items: list[dict] = []
    for placement in placements:
        after, lines = apply_placement(board, placement)
        items.append(
            {
                "board": [list(row) for row in after.occupancy()],
                "placement": {
                    "kind": placement.kind,
                    "rotation": placement.rotation,
                    "column": placement.column,
                    "row": placement.row,
                    "cells": [list(cell) for cell in placement.cells],
                    "lines_cleared": lines,
                },
            }
        )
    return items


class ScoringSandbox:
    """A live worker process running one model-written scoring function.

    Use as a context manager; the worker starts on entry and is shut down on
    exit even if the game raised.
    """

    def __init__(
        self,
        source: str,
        limits: SandboxLimits | None = None,
        validate: bool = True,
    ) -> None:
        self.source = source
        self.limits = limits or SandboxLimits()
        self.failures = 0
        self.errors: list[str] = []
        self._process: subprocess.Popen[str] | None = None
        self._started: float | None = None
        if validate:
            validate_source(source)

    @property
    def elapsed_seconds(self) -> float:
        """Wall-clock since the worker started, or 0 before it has."""
        if self._started is None:
            return 0.0
        return time.monotonic() - self._started

    def _check_game_deadline(self) -> None:
        """Refuse to start more work once the game's budget is spent.

        Checked before a batch rather than enforced during one. Cutting a batch
        short would mean killing a worker that is behaving exactly as the
        per-call budget allows, which is the same mistake ``per_batch_seconds``
        was widened to a floor to avoid -- and it would surface as a crash
        rather than as the deadline it really is. So the true bound is this
        budget plus at most one batch, which at the defaults is 300s + 44s.
        """
        budget = self.limits.per_game_seconds
        if budget is None or self._started is None:
            return
        elapsed = self.elapsed_seconds
        if elapsed > budget:
            raise SandboxGameDeadline(
                f"the game exceeded its {budget:g}s budget after {elapsed:.1f}s; "
                "the function is too slow to play a whole game"
            )

    def __enter__(self) -> ScoringSandbox:
        self._started = time.monotonic()
        self._process = subprocess.Popen(
            [sys.executable, "-I", str(WORKER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # Discarded on purpose: the function's own output is not data, and a
            # chatty function filling a pipe nobody drains would deadlock.
            stderr=subprocess.DEVNULL,
            text=True,
        )
        reply = self._exchange(
            {
                "op": "load",
                "source": self.source,
                "per_call_seconds": self.limits.per_call_seconds,
            },
            timeout=self.limits.load_seconds,
        )
        if not reply.get("ok"):
            self.close()
            raise SandboxValidationError(reply.get("error", "the function failed to load"))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Stop the worker, politely if it will go, forcibly if not."""
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.write(json.dumps({"op": "quit"}) + "\n")
                process.stdin.flush()
                process.stdin.close()
            process.wait(timeout=2.0)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()

    def score(self, items: Sequence[dict]) -> list[float]:
        """Score a piece's placements, in the order given.

        A placement whose scoring raised or timed out comes back as negative
        infinity, so it is never chosen, and the failure is counted. That keeps a
        function which is wrong on a few board shapes playable, which is the
        partial competence an improvement curve should be able to see.
        """
        if not items:
            return []
        self._check_game_deadline()
        reply = self._exchange(
            {"op": "score", "items": list(items)},
            timeout=self.limits.batch_deadline(len(items)),
        )
        if not reply.get("ok"):
            raise SandboxCrashed(reply.get("error", "scoring failed"))

        scores = reply["scores"]
        for index, error in enumerate(reply.get("errors") or []):
            if error is not None:
                self.failures += 1
                if len(self.errors) < 10:  # a sample is enough for feedback
                    self.errors.append(f"placement {index}: {error}")
        return [UNPLAYABLE if value is None else float(value) for value in scores]

    def _exchange(self, request: dict, timeout: float) -> dict:
        """Send one request and read one reply, or give up."""
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise SandboxCrashed("the sandbox is not running")

        try:
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, ValueError) as error:
            raise SandboxCrashed(f"the sandbox stopped accepting input: {error}") from error

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            if not selector.select(timeout):
                self.close()
                raise SandboxCrashed(f"the sandbox did not answer within {timeout}s")
            line = process.stdout.readline()
        finally:
            selector.close()

        if not line:
            self.close()
            raise SandboxCrashed("the sandbox exited without answering")
        try:
            return json.loads(line)
        except ValueError as error:
            raise SandboxCrashed(f"the sandbox sent malformed output: {error}") from error
