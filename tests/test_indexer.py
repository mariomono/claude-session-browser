from app import indexer


def _assistant(stop_reason="end_turn", usage=None, model="claude-opus-4-8"):
    return {
        "type": "assistant", "timestamp": "2026-05-30T10:00:00Z",
        "cwd": "/home/mario/projects/demo", "gitBranch": "main",
        "message": {"model": model, "stop_reason": stop_reason,
                    "usage": usage or {}, "content": [{"type": "text", "text": "ok"}]},
    }


def _user(text_str, ts="2026-05-30T09:59:00Z"):
    return {"type": "user", "timestamp": ts,
            "cwd": "/home/mario/projects/demo", "gitBranch": "main",
            "message": {"role": "user", "content": text_str}}


def test_index_file_basic_fields(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "My Session Title"},
        _user("the first prompt", ts="2026-05-30T09:00:00Z"),
        _assistant(usage={"input_tokens": 5, "cache_read_input_tokens": 45000,
                          "cache_creation_input_tokens": 5000}),
        _user("the last prompt", ts="2026-05-30T09:30:00Z"),
    ], session_id="sess1")
    idx = indexer.index_file(path)
    assert idx.session_id == "sess1"
    assert idx.title == "My Session Title"
    assert idx.first_prompt == "the first prompt"
    assert idx.last_prompt == "the last prompt"
    assert idx.cwd == "/home/mario/projects/demo"
    assert idx.git_branch == "main"
    assert idx.context_tokens == 50005
    assert idx.window_size == 200_000
    assert idx.model == "claude-opus-4-8"
    assert idx.outcome == "clean"
    assert idx.message_count == 3   # 2 user + 1 assistant


def test_title_falls_back_to_session_id(write_session):
    path = write_session([_user("hi"), _assistant()], session_id="no-title-here")
    idx = indexer.index_file(path)
    assert idx.title == "no-title-here"


def test_custom_title_overrides_ai_title(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "auto"},
        {"type": "custom-title", "customTitle": "MINE"},
        _user("hi"), _assistant(),
    ])
    assert indexer.index_file(path).title == "MINE"


def test_outcome_interrupted_on_dangling_tool_use(write_session):
    path = write_session([_user("hi"), _assistant(stop_reason="tool_use")])
    assert indexer.index_file(path).outcome == "interrupted"


def test_outcome_error_on_api_error(write_session):
    err = _assistant()
    err["message"]["isApiErrorMessage"] = True
    path = write_session([_user("hi"), err])
    assert indexer.index_file(path).outcome == "error"


def test_compacted_flag_and_1m_window(write_session):
    path = write_session([
        _user("hi"),
        {"type": "system", "compactMetadata": {"trigger": "auto"}},
        _assistant(usage={"input_tokens": 1, "cache_read_input_tokens": 300000,
                          "cache_creation_input_tokens": 0}),
    ])
    idx = indexer.index_file(path)
    assert idx.compacted is True
    assert idx.window_size == 1_000_000


def test_sidechain_records_excluded(write_session):
    side = _assistant()
    side["isSidechain"] = True
    path = write_session([_user("hi"), _assistant(), side])
    # only 1 user + 1 assistant counted, sidechain ignored
    assert indexer.index_file(path).message_count == 2


def test_last_prompt_field_preferred(write_session):
    path = write_session([
        _user("opening", ts="2026-05-30T09:00:00Z"),
        _assistant(),
        {"type": "last-prompt", "lastPrompt": "resume here please"},
    ])
    assert indexer.index_file(path).last_prompt == "resume here please"
    assert indexer.index_file(path).first_prompt == "opening"


def test_synthetic_model_ignored_for_model_and_usage(write_session):
    synth = _assistant(model="<synthetic>", usage={"input_tokens": 9})
    path = write_session([_user("hi"), synth])
    idx = indexer.index_file(path)
    assert idx.model is None
    assert idx.context_tokens is None
