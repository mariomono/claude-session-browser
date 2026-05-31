import json
import pytest


@pytest.fixture
def write_session(tmp_path):
    """Write a list of record dicts to a <project>/<session_id>.jsonl file."""
    def _write(records, project="-home-mario-projects-demo", session_id="sess1"):
        proj_dir = tmp_path / project
        proj_dir.mkdir(parents=True, exist_ok=True)
        path = proj_dir / f"{session_id}.jsonl"
        with path.open("w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return path
    return _write
