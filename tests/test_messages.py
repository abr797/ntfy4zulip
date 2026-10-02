import unittest
from datetime import datetime, timezone

from ntfy4zulip.messages import notification_text, preview_content
from ntfy4zulip.models import NotificationCandidate


class MessageTests(unittest.TestCase):
    def test_preview_collapses_whitespace_and_truncates(self):
        self.assertEqual(preview_content("hello\n\n world", 100), "hello world")
        self.assertEqual(preview_content("abcdef", 4), "abc…")

    def test_channel_title(self):
        candidate = NotificationCandidate(
            message_id=1,
            date_sent=datetime.now(timezone.utc),
            sender_id=10,
            sender_full_name="Alice",
            target_user_id=11,
            target_full_name="Bob",
            content="Deploy now",
            topic_name="backend",
            is_channel_message=True,
            stream_id=5,
            stream_name="development",
            dm_user_ids=(),
        )
        title, body = notification_text(candidate, 100)
        self.assertEqual(title, "Zulip · #development · backend")
        self.assertIn("Alice", body)
        self.assertIn("Deploy now", body)
