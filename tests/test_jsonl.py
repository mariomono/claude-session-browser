from app import jsonl


def test_read_records_parses_and_counts_bad(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(
        '{"type": "user", "n": 1}\n'
        '\n'                       # blank line ignored
        'not valid json\n'         # malformed -> counted
        '{"type": "assistant", "n": 2}\n'
    )
    records, bad = jsonl.read_records(f)
    assert [r["n"] for r in records] == [1, 2]
    assert bad == 1


def test_read_records_empty_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    records, bad = jsonl.read_records(f)
    assert records == []
    assert bad == 0


def test_iter_records_skips_malformed(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"a": 1}\nbad\n{"a": 2}\n')
    assert [r["a"] for r in jsonl.iter_records(f)] == [1, 2]
