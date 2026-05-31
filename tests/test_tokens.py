from app import tokens


def test_context_fill_sums_input_side_only():
    usage = {
        "input_tokens": 6,
        "cache_creation_input_tokens": 45351,
        "cache_read_input_tokens": 1000,
        "output_tokens": 9999,  # must be ignored
    }
    assert tokens.context_fill(usage) == 6 + 45351 + 1000


def test_context_fill_handles_none_and_missing():
    assert tokens.context_fill(None) == 0
    assert tokens.context_fill({}) == 0
    assert tokens.context_fill({"input_tokens": None}) == 0


def test_window_size_defaults_to_200k():
    assert tokens.window_size(150_000) == 200_000


def test_window_size_switches_to_1m_when_over_200k():
    assert tokens.window_size(200_001) == 1_000_000
    assert tokens.window_size(494_037) == 1_000_000


def test_context_pct():
    assert tokens.context_pct(50_000, 200_000) == 25.0
    assert tokens.context_pct(0, 200_000) == 0.0
    assert tokens.context_pct(100, 0) == 0.0
