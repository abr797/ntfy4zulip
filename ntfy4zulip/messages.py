from __future__ import annotations

import re

from .models import NotificationCandidate

_WHITESPACE = re.compile(r"\s+")


def preview_content(content: str, limit: int) -> str:
    text = _WHITESPACE.sub(" ", content).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def notification_text(candidate: NotificationCandidate, preview_chars: int) -> tuple[str, str]:
    body = preview_content(candidate.content, preview_chars)
    if candidate.is_channel_message:
        stream = candidate.stream_name or "unknown channel"
        topic = candidate.topic_name or "general chat"
        title = f"Zulip · #{stream} · {topic}"
    else:
        title = f"Zulip · {candidate.sender_full_name}"

    if body:
        message = f"**{candidate.sender_full_name}:** {body}"
    else:
        message = f"**{candidate.sender_full_name}** sent a message"
    return title, message
