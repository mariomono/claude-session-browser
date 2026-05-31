from app import parser


def test_parse_transcript_entries(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "Demo"},
        {"type": "user", "timestamp": "t1", "cwd": "/home/mario/projects/demo",
         "message": {"role": "user", "content": "please help"}},
        {"type": "assistant", "timestamp": "t2", "cwd": "/home/mario/projects/demo",
         "message": {"model": "claude-opus-4-8", "stop_reason": "tool_use",
                     "usage": {"input_tokens": 1, "cache_read_input_tokens": 100,
                               "cache_creation_input_tokens": 0},
                     "content": [
                         {"type": "thinking", "thinking": "let me think"},
                         {"type": "text", "text": "I'll run a command"},
                         {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                     ]}},
        {"type": "user", "timestamp": "t3", "cwd": "/home/mario/projects/demo",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "content": "file1\nfile2"}]}},
    ])
    tr = parser.parse_transcript(path)
    assert tr.title == "Demo"
    assert tr.model == "claude-opus-4-8"
    assert tr.context_tokens == 101
    kinds = [(e.role, e.kind) for e in tr.entries]
    assert ("user", "text") in kinds
    assert ("assistant", "thinking") in kinds
    assert ("assistant", "text") in kinds
    assert ("assistant", "tool_use") in kinds
    assert ("user", "tool_result") in kinds
    tool = next(e for e in tr.entries if e.kind == "tool_use")
    assert tool.tool_name == "Bash"
    assert "ls" in tool.content


def test_parse_transcript_compact_summary_as_system_note(write_session):
    path = write_session([
        {"type": "user", "timestamp": "t1", "isCompactSummary": True,
         "message": {"role": "user", "content": "summary of prior work"}},
    ])
    tr = parser.parse_transcript(path)
    assert tr.entries[0].role == "system"
    assert tr.entries[0].kind == "system_note"
    assert "compaction summary" in tr.entries[0].content


def test_parse_transcript_marks_sidechain(write_session):
    path = write_session([
        {"type": "assistant", "timestamp": "t1", "isSidechain": True,
         "message": {"model": "claude-opus-4-8", "stop_reason": "end_turn",
                     "content": [{"type": "text", "text": "subagent output"}]}},
    ])
    tr = parser.parse_transcript(path)
    assert tr.entries[0].is_sidechain is True
