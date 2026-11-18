"""Tests for JSONL reading and writing."""

import json
from dataclasses import dataclass
from typing import Any

import pytest

from tetris_bench.jsonl import JsonlWriter, append_record, read_records


@dataclass(frozen=True)
class Row:
    """A minimal stand-in for a real record."""

    n: int

    def as_dict(self) -> dict[str, Any]:
        return {"n": self.n}


class TestAppendRecord:
    def test_writes_one_json_object_per_line(self, tmp_path):
        path = tmp_path / "out.jsonl"
        append_record(path, Row(1))
        append_record(path, Row(2))
        lines = path.read_text().strip().splitlines()
        assert [json.loads(line) for line in lines] == [{"n": 1}, {"n": 2}]

    def test_appends_rather_than_overwrites(self, tmp_path):
        path = tmp_path / "out.jsonl"
        for n in range(5):
            append_record(path, Row(n))
        assert len(path.read_text().strip().splitlines()) == 5

    def test_creates_missing_parent_directories(self, tmp_path):
        path = tmp_path / "runs" / "nested" / "out.jsonl"
        append_record(path, Row(1))
        assert path.exists()

    def test_accepts_a_string_path(self, tmp_path):
        path = tmp_path / "out.jsonl"
        append_record(str(path), Row(1))
        assert path.exists()

    def test_keys_are_sorted_on_disk_for_stable_diffs(self, tmp_path):
        """Field order in a record must not change the bytes written."""

        @dataclass(frozen=True)
        class Unordered:
            def as_dict(self) -> dict[str, Any]:
                return {"z": 1, "a": 2}

        path = tmp_path / "out.jsonl"
        append_record(path, Unordered())
        assert path.read_text().strip() == '{"a": 2, "z": 1}'


class TestReadRecords:
    def test_round_trips(self, tmp_path):
        path = tmp_path / "out.jsonl"
        for n in range(3):
            append_record(path, Row(n))
        assert list(read_records(path)) == [{"n": 0}, {"n": 1}, {"n": 2}]

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "out.jsonl"
        path.write_text('{"n": 1}\n\n{"n": 2}\n\n')
        assert list(read_records(path)) == [{"n": 1}, {"n": 2}]

    def test_yields_plain_dicts(self, tmp_path):
        path = tmp_path / "out.jsonl"
        append_record(path, Row(1))
        assert all(isinstance(row, dict) for row in read_records(path))

    def test_is_lazy(self, tmp_path):
        """A long run's log should stream, not load whole."""
        path = tmp_path / "out.jsonl"
        append_record(path, Row(1))
        records = read_records(path)
        assert not isinstance(records, list)
        assert next(records) == {"n": 1}

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list(read_records(tmp_path / "nope.jsonl"))


class TestJsonlWriter:
    def test_writes_many_records(self, tmp_path):
        path = tmp_path / "out.jsonl"
        with JsonlWriter(path) as writer:
            for n in range(4):
                writer.write(Row(n))
        assert list(read_records(path)) == [{"n": n} for n in range(4)]

    def test_flushes_each_record_so_a_crash_cannot_lose_it(self, tmp_path):
        path = tmp_path / "out.jsonl"
        with JsonlWriter(path) as writer:
            writer.write(Row(1))
            # readable from outside the still-open writer
            assert list(read_records(path)) == [{"n": 1}]

    def test_appends_to_an_existing_file(self, tmp_path):
        path = tmp_path / "out.jsonl"
        append_record(path, Row(0))
        with JsonlWriter(path) as writer:
            writer.write(Row(1))
        assert list(read_records(path)) == [{"n": 0}, {"n": 1}]

    def test_creates_missing_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "out.jsonl"
        with JsonlWriter(path) as writer:
            writer.write(Row(1))
        assert path.exists()

    def test_refuses_to_write_outside_a_context_manager(self, tmp_path):
        writer = JsonlWriter(tmp_path / "out.jsonl")
        with pytest.raises(RuntimeError, match="context manager"):
            writer.write(Row(1))
