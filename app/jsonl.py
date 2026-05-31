"""Streaming and buffered readers for Claude Code session .jsonl files."""
import json
from pathlib import Path
from typing import Iterator


def iter_records(path: Path) -> Iterator[dict]:
    """Yield parsed JSON objects, skipping blank and malformed lines.

    Append-only logs can end with a partial write; such lines are skipped.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_records(path: Path) -> tuple[list[dict], int]:
    """Return (records, unparsable_line_count)."""
    records: list[dict] = []
    bad = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return records, bad
