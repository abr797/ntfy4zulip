import asyncio
import unittest
from datetime import datetime, timezone

from ntfy4zulip.models import NotificationCandidate
from ntfy4zulip.poller import NotificationPoller


class FakeDatabase:
    def __init__(self, candidates=None, error=None):
        self.candidates = candidates or []
        self.error = error
        self.calls = 0

    def fetch_candidates(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.candidates


class FakeNtfy:
    def __init__(self):
        self.calls = []

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        return True


def channel_candidate(**overrides):
    values = dict(
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
    values.update(overrides)
    return NotificationCandidate(**values)


class PollerTests(unittest.IsolatedAsyncioTestCase):
    def make_poller(self, database, ntfy=None):
        return NotificationPoller(
            database=database,
            ntfy=ntfy or FakeNtfy(),
            zulip_site="https://chat.example",
            topic_secret="x" * 32,
            topic_prefix="zulip",
        )

    async def test_scan_sends_one_push_per_candidate_without_browser_click(self):
        ntfy = FakeNtfy()
        poller = self.make_poller(FakeDatabase([channel_candidate()]), ntfy)
        sent, failed = await poller.scan_once()
        self.assertEqual((sent, failed), (1, 0))
        self.assertEqual(len(ntfy.calls), 1)
        self.assertNotIn("click", ntfy.calls[0])
        self.assertEqual(ntfy.calls[0]["source"], "poller")
        self.assertEqual(ntfy.calls[0]["message_id"], 100)
        self.assertEqual(ntfy.calls[0]["user_id"], 2)

    async def test_duplicate_pair_in_same_scan_is_suppressed(self):
        c = channel_candidate()
        ntfy = FakeNtfy()
        poller = self.make_poller(FakeDatabase([c, c]), ntfy)
        sent, failed = await poller.scan_once()
        self.assertEqual((sent, failed), (1, 0))
        self.assertEqual(len(ntfy.calls), 1)

    async def test_malformed_candidate_does_not_block_good_candidate(self):
        malformed = channel_candidate(message_id=99, target_user_id=0)
        good = channel_candidate(message_id=100)
        ntfy = FakeNtfy()
        poller = self.make_poller(FakeDatabase([malformed, good]), ntfy)
        sent, failed = await poller.scan_once()
        self.assertEqual((sent, failed), (1, 1))
        self.assertEqual(len(ntfy.calls), 1)

    async def test_database_failure_does_not_terminate_run_loop(self):
        database = FakeDatabase(error=RuntimeError("database offline"))
        poller = self.make_poller(database)
        poller._seconds_until_next_tick = lambda: 0.01

        stop_event = asyncio.Event()
        task = asyncio.create_task(poller.run(stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)

        self.assertGreater(database.calls, 0)

    async def test_stop_event_exits_without_scanning(self):
        database = FakeDatabase([channel_candidate()])
        poller = self.make_poller(database)
        stop_event = asyncio.Event()
        stop_event.set()
        await asyncio.wait_for(poller.run(stop_event), timeout=1)
        self.assertEqual(database.calls, 0)
