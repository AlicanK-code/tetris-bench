"""Appending run records to JSONL files.

JSONL -- one JSON object per line -- because runs are append-only and long. A
crashed run leaves every completed game already on disk and readable, which a
single JSON array would not: an unterminated array is unparseable, so you would
lose the whole file. It also streams into pandas directly.

This module is the only place that touches the filesystem, which keeps
:mod:`tetris_bench.metrics` and :mod:`tetris_bench.records` pure and trivially
testable.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol


class Record(Protocol):
    """Anything that can flatten itself into one JSON object."""

    def as_dict(self) -> dict[str, Any]:
        """The record as a single-level dict."""
        ...


def append_record(path: Path | str, record: Record) -> None:
    """Append one record to ``path``, creating parent directories as needed.

    Opened and closed per call, which is the right trade for a few hundred games:
    a run that dies mid-way has already flushed everything before it.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.as_dict(), sort_keys=True) + "\n")


def read_records(path: Path | str) -> Iterator[dict[str, Any]]:
    """Read records back, skipping blank and unparseable lines.

    Yields plain dicts rather than reconstructing dataclasses: the analysis layer
    wants a dataframe, and the schema on disk is allowed to outlive any one
    version of the code that wrote it.

    Unparseable lines are skipped rather than raising, because that is the whole
    reason for choosing JSONL: a run killed mid-write leaves a truncated final
    line, and every completed record before it must still be readable. Raising
    there would throw away the property the format was chosen for.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


class JsonlWriter:
    """A context manager that holds the file open across many records.

    Worth using when a run writes frequently; :func:`append_record` is fine for
    one-off writes.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._handle = None

    def __enter__(self) -> JsonlWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def write(self, record: Record) -> None:
        """Write one record and flush it, so a crash cannot lose it."""
        if self._handle is None:
            raise RuntimeError("JsonlWriter must be used as a context manager")
        self._handle.write(json.dumps(record.as_dict(), sort_keys=True) + "\n")
        self._handle.flush()
