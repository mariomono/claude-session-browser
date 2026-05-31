"""Pure helpers for extracting and trimming text from message records."""


def message_text(message: dict) -> str:
    """Flatten a message's content into plain text (text blocks only)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return ""


def truncate(text_in: str, limit: int = 200) -> str:
    """Collapse whitespace and cap length with an ellipsis."""
    collapsed = " ".join((text_in or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def is_real_user_prompt(message: dict) -> bool:
    """True if the message carries actual typed user text (not a tool_result)."""
    content = message.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and (block.get("text") or "").strip()
            ):
                return True
    return False
