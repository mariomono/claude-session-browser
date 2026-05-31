from app import text


def test_message_text_from_string():
    assert text.message_text({"content": "hello"}) == "hello"


def test_message_text_from_blocks_joins_text_only():
    msg = {"content": [
        {"type": "text", "text": "first"},
        {"type": "tool_use", "name": "Bash", "input": {}},
        {"type": "text", "text": "second"},
    ]}
    assert text.message_text(msg) == "first\nsecond"


def test_message_text_missing_content():
    assert text.message_text({}) == ""


def test_truncate_collapses_whitespace_and_limits():
    assert text.truncate("a\n\n  b   c") == "a b c"
    long = "x" * 300
    out = text.truncate(long, 200)
    assert len(out) == 200 and out.endswith("…")


def test_is_real_user_prompt():
    assert text.is_real_user_prompt({"content": "do a thing"}) is True
    assert text.is_real_user_prompt({"content": "   "}) is False
    assert text.is_real_user_prompt({"content": [
        {"type": "tool_result", "content": "output"}]}) is False
    assert text.is_real_user_prompt({"content": [
        {"type": "text", "text": "real prompt"}]}) is True
