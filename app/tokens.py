"""Token-usage and context-window math for Claude session logs."""

DEFAULT_WINDOW = 200_000
LARGE_WINDOW = 1_000_000


def context_fill(usage: dict | None) -> int:
    """Input-side token count for a single assistant usage block.

    This equals the size of the prompt sent for that request, i.e. how full
    the context window was at that turn. Output tokens are excluded on purpose,
    and we never sum across messages.
    """
    if not isinstance(usage, dict):
        return 0
    return (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )


def window_size(observed_tokens: int) -> int:
    """Context window size: 200k default, 1M if usage exceeds 200k.

    The JSONL does not record the 1M-beta header, so exceeding the standard
    window is the only reliable signal that the larger window was active.
    """
    return LARGE_WINDOW if observed_tokens > DEFAULT_WINDOW else DEFAULT_WINDOW


def context_pct(tokens_used: int, window: int) -> float:
    if window <= 0:
        return 0.0
    return round(100.0 * tokens_used / window, 1)
