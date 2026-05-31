from pathlib import Path
import pytest
from app import indexer, parser

ROOT = Path.home() / ".claude" / "projects"


@pytest.mark.skipif(not ROOT.exists(), reason="no real Claude logs present")
def test_real_index_builds(tmp_path):
    sessions = indexer.build_index(ROOT, tmp_path / "cache.json")
    assert len(sessions) > 0
    # newest first
    acts = [s.last_activity or "" for s in sessions]
    assert acts == sorted(acts, reverse=True)
    # every session has a title and valid outcome
    valid = {"clean", "interrupted", "error", "unknown"}
    for s in sessions:
        assert s.title
        assert s.outcome in valid


@pytest.mark.skipif(not ROOT.exists(), reason="no real Claude logs present")
def test_real_transcript_parses(tmp_path):
    sessions = indexer.build_index(ROOT, tmp_path / "cache.json")
    path = indexer.find_session_path(ROOT, sessions[0].session_id)
    assert path is not None
    tr = parser.parse_transcript(path)
    assert tr.session_id == sessions[0].session_id
