import unittest
from datetime import datetime, timezone

from ntfy4zulip.models import NotificationCandidate
from ntfy4zulip.poller import NotificationPoller


class FakeDatabase:
    def __init__(self, candidates):
        self.candidates = candidates

    def fetch_candidates(self):
        return self.candidates


class FakeNtfy:
    def __init__(self):
        self.calls = []

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        return True


class PollerTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_sends_one_push_per_candidate(self):
        c = NotificationCandidate(
            message_id=100,
            date_sent=datetime.now(timezone.utc),
            sender_id=1,
            sender_full_name="Alice",
            target_user_id=2,
            target_full_name="Bob",
            content="hello",
            topic_name="backend",
            is_channel_message=True,
            stream_id=3,
            stream_name="dev",
            dm_user_ids=(),
        )
        ntfy = FakeNtfy()
        poller = NotificationPoller(
            database=FakeDatabase([c]),
            ntfy=ntfy,
            zulip_site="https://chat.example",
            topic_secret="x" * 32,
            topic_prefix="zulip",
        )
        sent, failed = await poller.scan_once()
        self.assertEqual((sent, failed), (1, 0))
        self.assertEqual(len(ntfy.calls), 1)
        self.assertIn("/#narrow/channel/", ntfy.calls[0]["click"])

    async def test_duplicate_pair_in_same_scan_is_suppressed(self):
        c = NotificationCandidate(
            message_id=100,
            date_sent=datetime.now(timezone.utc),
            sender_id=1,
            sender_full_name="Alice",
            target_user_id=2,
            target_full_name="Bob",
            content="hello",
            topic_name="backend",
            is_channel_message=True,
            stream_id=3,
            stream_name="dev",
            dm_user_ids=(),
        )
        ntfy = FakeNtfy()
        poller = NotificationPoller(
            database=FakeDatabase([c, c]),
            ntfy=ntfy,
            zulip_site="https://chat.example",
            topic_secret="x" * 32,
            topic_prefix="zulip",
        )
        sent, failed = await poller.scan_once()
        self.assertEqual((sent, failed), (1, 0))
