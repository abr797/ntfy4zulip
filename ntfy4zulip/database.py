from __future__ import annotations

from collections.abc import Mapping

from .models import NotificationCandidate

# Zulip Server 12.2: UserMessage.flags bit 0 is "read".
# We intentionally only consider rows for which UserMessage exists. This means
# ordinary channel traffic for long_term_idle users may be omitted, matching the
# project's deliberate MVP constraint.
UNREAD_NOTIFICATION_QUERY = r"""
SELECT
    m.id AS message_id,
    m.date_sent,
    m.sender_id,
    sender.full_name AS sender_full_name,
    um.user_profile_id AS target_user_id,
    target.full_name AS target_full_name,
    m.content,
    m.subject AS topic_name,
    m.is_channel_message,
    stream.id AS stream_id,
    stream.name AS stream_name,
    CASE
        WHEN m.is_channel_message THEN NULL
        ELSE ARRAY(
            SELECT dm_sub.user_profile_id
            FROM zerver_subscription AS dm_sub
            WHERE dm_sub.recipient_id = m.recipient_id
            ORDER BY dm_sub.user_profile_id
        )
    END AS dm_user_ids
FROM zerver_message AS m
JOIN zerver_usermessage AS um
    ON um.message_id = m.id
JOIN zerver_userprofile AS sender
    ON sender.id = m.sender_id
JOIN zerver_userprofile AS target
    ON target.id = um.user_profile_id
JOIN zerver_recipient AS recipient
    ON recipient.id = m.recipient_id
LEFT JOIN zerver_stream AS stream
    ON m.is_channel_message
   AND recipient.type = 2
   AND stream.id = recipient.type_id
WHERE
    m.date_sent >= date_trunc('minute', CURRENT_TIMESTAMP)
                   - (%s + 1) * INTERVAL '1 minute'
    AND m.date_sent < date_trunc('minute', CURRENT_TIMESTAMP)
                      - %s * INTERVAL '1 minute'
    AND (um.flags & 1) = 0
    AND um.user_profile_id <> m.sender_id
    AND target.is_active = TRUE
    AND target.is_bot = FALSE
    AND m.realm_id = (
        SELECT realm_id
        FROM zerver_userprofile
        WHERE id = %s
    )
ORDER BY m.id, um.user_profile_id
"""


def _candidate_from_row(row: Mapping[str, object]) -> NotificationCandidate:
    raw_ids = row.get("dm_user_ids") or []
    return NotificationCandidate(
        message_id=int(row["message_id"]),
        date_sent=row["date_sent"],  # type: ignore[arg-type]
        sender_id=int(row["sender_id"]),
        sender_full_name=str(row["sender_full_name"]),
        target_user_id=int(row["target_user_id"]),
        target_full_name=str(row["target_full_name"]),
        content=str(row.get("content") or ""),
        topic_name=str(row.get("topic_name") or ""),
        is_channel_message=bool(row["is_channel_message"]),
        stream_id=int(row["stream_id"]) if row.get("stream_id") is not None else None,
        stream_name=str(row["stream_name"]) if row.get("stream_name") is not None else None,
        dm_user_ids=tuple(int(user_id) for user_id in raw_ids),
    )


class ZulipDatabase:
    def __init__(self, dsn: str, realm_anchor_user_id: int, delay_minutes: int = 3):
        self.dsn = dsn
        self.realm_anchor_user_id = realm_anchor_user_id
        self.delay_minutes = delay_minutes

    def fetch_candidates(self) -> list[NotificationCandidate]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                with conn.cursor() as cur:
                    cur.execute(
                        UNREAD_NOTIFICATION_QUERY,
                        (
                            self.delay_minutes,
                            self.delay_minutes,
                            self.realm_anchor_user_id,
                        ),
                    )
                    rows = cur.fetchall()
        return [_candidate_from_row(row) for row in rows]
