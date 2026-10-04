from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NotificationCandidate:
    message_id: int
    date_sent: datetime
    sender_id: int
    sender_full_name: str
    target_user_id: int
    target_full_name: str
    content: str
    topic_name: str
    is_channel_message: bool
    stream_id: int | None
    stream_name: str | None
    dm_user_ids: tuple[int, ...]
