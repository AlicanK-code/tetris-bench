"""The isolated child process that runs model-written scoring functions.

This file is **executed by path**, never imported, and deliberately uses nothing
but the standard library. The host launches it as::

    python -I <path to this file>

``-I`` is isolated mode: it implies ``-E`` (ignore ``PYTHON*`` environment
variables), ``-s`` (no user site directory) and ``-P`` (do not put the script's
own directory on ``sys.path``). Together with importing no project module, that
means the model's code runs in an interpreter where ``tetris_bench`` is not
importable and nothing of the host's state exists to reach.

Three further defences, since process isolation alone only limits the damage:

- the function is executed with a small allowlist of builtins, so ``open``,
  ``__import__``, ``eval`` and friends are simply absent from its namespace;
- ``math`` is pre-injected rather than importable, so the one pure module the
  function may want is available without permitting an import statement;
- each call is bounded by ``SIGALRM``, so an infinite loop in pure Python is
  interrupted and reported rather than hanging the run.

The host validates the source with an AST allowlist *before* sending it here;
this process assumes that has happened and is the containment layer, not the
first line of defence.

Protocol: one JSON object per line on stdin, one JSON object per line on stdout.

    {"op": "load",  "source": "...", "per_call_seconds": 1.0}
        -> {"ok": true} | {"ok": false, "error": "..."}
    {"op": "score", "items": [{"board": [[bool, ...], ...], "placement": {...}}]}
        -> {"ok": true, "scores": [float|null, ...], "errors": [str|null, ...]}
    {"op": "quit"}
        -> (exits)

A ``null`` score means that placement raised or timed out. The host turns those
into a score of negative infinity, so the move is never chosen, and counts the
failure. A function that is wrong on a few board shapes still produces a
measurable game, which is the partial competence an improvement curve should see.
"""

import json
import math
import signal
import sys

FUNCTION_NAME = "score"

# Everything the function is allowed to reach. Anything absent from this mapping
# does not exist inside the sandbox, which is a stronger guarantee than trying to
# forbid it after the fact.
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    # Exception types, so model code can raise and catch normally. These touch
    # nothing outside the process; without them even `except ValueError` would
    # itself fail with a NameError.
    "ArithmeticError": ArithmeticError,
    "AttributeError": AttributeError,
    "Exception": Exception,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "OverflowError": OverflowError,
    "StopIteration": StopIteration,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "ZeroDivisionError": ZeroDivisionError,
    # Allowed deliberately, even though the prompt asks for no printing: adding a
    # debug print is a reflex, and making it a NameError would fail every
    # placement and read as a strategy failure rather than a stray line. It is
    # harmless because this process sends the function's stdout to stderr, so it
    # cannot reach the protocol channel.
    "print": print,
}


class CallTimeout(BaseException):
    """Raised inside the sandbox when one call exceeds its time budget.

    Derives from :class:`BaseException`, not :class:`Exception`, and that is
    load-bearing. A scoring function containing a broad ``except Exception:``
    inside a loop -- an ordinary defensive pattern -- would otherwise swallow its
    own timeout. ``signal.setitimer`` is one-shot, so no second alarm fires, and
    the function would then spin until the host's batch deadline killed the
    worker and aborted the whole run.
    """


def _on_alarm(_signum: int, _frame: object) -> None:
    raise CallTimeout("exceeded the per-call time limit")


def _freeze_board(rows: list) -> tuple:
    """Hand the function immutable rows, so it cannot corrupt its own input."""
    return tuple(tuple(bool(cell) for cell in row) for row in rows)


def _freeze_placement(placement: dict) -> dict:
    """Copy the placement, with its cells as tuples."""
    frozen = dict(placement)
    if "cells" in frozen:
        frozen["cells"] = tuple(tuple(cell) for cell in frozen["cells"])
    return frozen


def load(source: str) -> object:
    """Compile and exec the source, returning the ``score`` function it defines."""
    namespace: dict = {"__builtins__": SAFE_BUILTINS, "math": math}
    exec(compile(source, "<model>", "exec"), namespace)  # noqa: S102
    function = namespace.get(FUNCTION_NAME)
    if function is None:
        raise ValueError(f"source defines no function called {FUNCTION_NAME!r}")
    if not callable(function):
        raise TypeError(f"{FUNCTION_NAME!r} is not callable")
    return function


def score_items(function: object, items: list, per_call_seconds: float) -> tuple:
    """Score every item, recording a failure rather than raising."""
    scores: list = []
    errors: list = []

    for item in items:
        board = _freeze_board(item["board"])
        placement = _freeze_placement(item["placement"])
        signal.setitimer(signal.ITIMER_REAL, per_call_seconds)
        try:
            value = function(board, placement)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"returned {type(value).__name__}, expected a number")
            value = float(value)
            if value != value:  # NaN would make max() arbitrary
                raise ValueError("returned NaN")
            scores.append(value)
            errors.append(None)
        except CallTimeout as error:
            # Handled explicitly: it is a BaseException precisely so that model
            # code cannot catch it, which means we must.
            scores.append(None)
            errors.append(f"CallTimeout: {error}")
        except Exception as error:
            scores.append(None)
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    return scores, errors


def main() -> int:
    # A stray print() in model code must not corrupt the protocol, so the
    # function's stdout goes to stderr and the protocol keeps the real one.
    protocol_out = sys.stdout
    sys.stdout = sys.stderr

    signal.signal(signal.SIGALRM, _on_alarm)

    function = None
    per_call_seconds = 1.0

    def reply(payload: dict) -> None:
        protocol_out.write(json.dumps(payload) + "\n")
        protocol_out.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except ValueError as error:
            reply({"ok": False, "error": f"malformed request: {error}"})
            continue

        op = request.get("op")

        if op == "quit":
            return 0

        if op == "load":
            per_call_seconds = float(request.get("per_call_seconds", 1.0))
            try:
                function = load(request["source"])
            except BaseException as error:  # noqa: BLE001 - any failure is a load failure
                function = None
                reply({"ok": False, "error": f"{type(error).__name__}: {error}"})
            else:
                reply({"ok": True})
            continue

        if op == "score":
            if function is None:
                reply({"ok": False, "error": "no function loaded"})
                continue
            scores, errors = score_items(function, request["items"], per_call_seconds)
            reply({"ok": True, "scores": scores, "errors": errors})
            continue

        reply({"ok": False, "error": f"unknown op {op!r}"})

    return 0


if __name__ == "__main__":
    sys.exit(main())
