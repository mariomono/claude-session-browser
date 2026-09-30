"""Persist the set of bookmarked session IDs in a JSON file."""

import json
from pathlib import Path


def load(path: Path) -> set[str]:
    """Read the bookmark set; empty on missing/malformed/non-list file."""
    try:
        data = json.loads(Path(path).read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(x) for x in data}


def save(path: Path, ids: set[str]) -> None:
    """Write the bookmark set, creating the parent directory if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ids)))


def toggle(path: Path, session_id: str) -> bool:
    """Add the id if absent, remove it if present. Return the new state."""
    ids = load(path)
    if session_id in ids:
        ids.discard(session_id)
        now = False
    else:
        ids.add(session_id)
        now = True
    save(path, ids)
    return now
