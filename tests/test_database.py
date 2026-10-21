import unittest
from datetime import datetime, timezone

from ntfy4zulip.database import (
    UNREAD_NOTIFICATION_QUERY,
    UNREAD_RECHECK_QUERY,
    _candidate_from_row,
)


class DatabaseTests(unittest.TestCase):
    def test_query_uses_unread_flag_and_closed_bucket(self):
        self.assertIn("(um.flags & 1) = 0", UNREAD_NOTIFICATION_QUERY)
        self.assertIn("date_trunc('minute', CURRENT_TIMESTAMP)", UNREAD_NOTIFICATION_QUERY)
        self.assertIn("target.is_active = TRUE", UNREAD_NOTIFICATION_QUERY)
        self.assertIn("m.realm_id", UNREAD_NOTIFICATION_QUERY)

    def test_recheck_uses_exact_pairs_and_unread_bit(self):
        self.assertIn("unnest(%s::bigint[], %s::bigint[])", UNREAD_RECHECK_QUERY)
        self.assertIn("um.message_id = requested.message_id", UNREAD_RECHECK_QUERY)
        self.assertIn("um.user_profile_id = requested.user_profile_id", UNREAD_RECHECK_QUERY)
        self.assertIn("(um.flags & 1) = 0", UNREAD_RECHECK_QUERY)

    def test_row_mapping(self):
        c = _candidate_from_row(
            {
                "message_id": 1,
                "date_sent": datetime.now(timezone.utc),
                "sender_id": 10,
                "sender_full_name": "Alice",
                "target_user_id": 11,
                "target_full_name": "Bob",
                "content": "hello",
                "topic_name": "topic",
                "is_channel_message": False,
                "stream_id": None,
                "stream_name": None,
                "dm_user_ids": [10, 11],
            }
        )
        self.assertEqual(c.dm_user_ids, (10, 11))
        self.assertEqual(c.target_user_id, 11)
