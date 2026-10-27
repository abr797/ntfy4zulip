import asyncio
import unittest
from datetime import datetime, timezone

from ntfy4zulip.models import NotificationCandidate
from ntfy4zulip.poller import NotificationPoller


class FakeDatabase:
    def __init__(self, candidates=None, error=None, still_unread=None, recheck_error=None):
        self.candidates = candidates or []
        self.error = error
        self.still_unread = still_unread
        self.recheck_error = recheck_error
        self.calls = 0
        self.recheck_calls = []

    def fetch_candidates(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.candidates

    def recheck_unread(self, pairs):
        self.recheck_calls.append(list(pairs))
        if self.recheck_error is not None:
            raise self.recheck_error
        return set(pairs) if self.still_unread is None else self.still_unread


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
    folder_name=None,
    user_message_flags=0,
    )
    values.update(overrides)
    return NotificationCandidate(**values)


class PollerTests(unittest.IsolatedAsyncioTestCase):
    def make_poller(
        self,
        database,
        ntfy=None,
        *,
        folder_priorities=None,
        default_priority=2,
        mention_priority=4,
        wildcard_mention_priority=3,
        dm_priority=4,
        group_dm_priority=3,
    ):
        return NotificationPoller(
            database=database,
            ntfy=ntfy or FakeNtfy(),
            zulip_site="https://chat.example",
            topic_secret="x" * 32,
            topic_prefix="zulip",
            default_priority=default_priority,
            mention_priority=mention_priority,
            wildcard_mention_priority=wildcard_mention_priority,
            dm_priority=dm_priority,
            group_dm_priority=group_dm_priority,
            folder_priorities=folder_priorities,
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
        self.assertEqual(ntfy.calls[0]["priority"], 2)

    async def test_global_folder_priority_applies_to_every_recipient(self):
        ntfy = FakeNtfy()
        database = FakeDatabase([
            channel_candidate(message_id=101, target_user_id=2, folder_name="Operations"),
            channel_candidate(message_id=101, target_user_id=3, folder_name="Operations"),
        ])
        poller = self.make_poller(database, ntfy, folder_priorities={"operations": 5})
        self.assertEqual(await poller.scan_once(), (2, 0))
        self.assertEqual([call["priority"] for call in ntfy.calls], [5, 5])

    async def test_unconfigured_folder_uses_channel_default_and_dm_ignores_folders(self):
        ntfy = FakeNtfy()
        database = FakeDatabase([
            channel_candidate(message_id=101, folder_name="Other"),
            channel_candidate(message_id=102, folder_name=None),
            channel_candidate(
                message_id=103,
                is_channel_message=False,
                dm_user_ids=(1, 2, 3),
                folder_name="Operations",
            ),
        ])
        poller = self.make_poller(
            database,
            ntfy,
            folder_priorities={"Operations": 5},
            default_priority=2,
        )
        self.assertEqual(await poller.scan_once(), (3, 0))
        self.assertEqual([call["priority"] for call in ntfy.calls], [2, 2, 3])

    async def test_type_priority_then_folder_only_escalates(self):
        ntfy = FakeNtfy()
        cases = [
            channel_candidate(message_id=201, folder_name="Quiet"),
            channel_candidate(message_id=202, folder_name="Critical"),
            channel_candidate(message_id=203, folder_name="Quiet", user_message_flags=1 << 3),
            channel_candidate(message_id=204, folder_name="Critical", user_message_flags=1 << 3),
            channel_candidate(message_id=205, folder_name="Quiet", user_message_flags=1 << 4),
            channel_candidate(message_id=206, folder_name="Critical", user_message_flags=1 << 5),
            channel_candidate(message_id=207, folder_name="Quiet", user_message_flags=1 << 6),
            channel_candidate(
                message_id=208,
                folder_name="Quiet",
                user_message_flags=(1 << 3) | (1 << 4),
            ),
        ]
        poller = self.make_poller(
            FakeDatabase(cases),
            ntfy,
            folder_priorities={"quiet": 1, "CRITICAL": 5},
        )
        self.assertEqual(await poller.scan_once(), (len(cases), 0))
        self.assertEqual(
            [call["priority"] for call in ntfy.calls],
            [2, 5, 4, 5, 3, 5, 4, 4],
        )

    async def test_one_to_one_and_group_dm_have_distinct_priority(self):
        ntfy = FakeNtfy()
        cases = [
            channel_candidate(
                message_id=300, is_channel_message=False, dm_user_ids=(1, 2)
            ),
            channel_candidate(
                message_id=301, is_channel_message=False, dm_user_ids=(1, 2, 3)
            ),
        ]
        poller = self.make_poller(
            FakeDatabase(cases),
            ntfy,
            folder_priorities={"Critical": 5},
        )
        self.assertEqual(await poller.scan_once(), (2, 0))
        self.assertEqual([call["priority"] for call in ntfy.calls], [4, 3])

    async def test_unknown_dm_participants_keep_higher_dm_priority(self):
        ntfy = FakeNtfy()
        cases = [channel_candidate(message_id=400, is_channel_message=False)]
        poller = self.make_poller(FakeDatabase(cases), ntfy)
        self.assertEqual(await poller.scan_once(), (1, 0))
        self.assertEqual(ntfy.calls[0]["priority"], 4)

    async def test_custom_type_priority_values(self):
        ntfy = FakeNtfy()
        cases = [
            channel_candidate(message_id=301, user_message_flags=(1 << 3) | (1 << 4)),
            channel_candidate(message_id=302, user_message_flags=1 << 3),
            channel_candidate(message_id=303, user_message_flags=1 << 5),
        ]
        poller = self.make_poller(
            FakeDatabase(cases),
            ntfy,
            mention_priority=2,
            wildcard_mention_priority=5,
        )
        self.assertEqual(await poller.scan_once(), (3, 0))
        self.assertEqual([call["priority"] for call in ntfy.calls], [5, 2, 5])

    async def test_message_read_after_scan_is_not_published(self):
        ntfy = FakeNtfy()
        database = FakeDatabase([channel_candidate()], still_unread=set())
        poller = self.make_poller(database, ntfy)

        with self.assertLogs("ntfy4zulip.poller", level="INFO") as captured:
            self.assertEqual(await poller.scan_once(), (0, 0))

        self.assertEqual(ntfy.calls, [])
        self.assertEqual(database.recheck_calls, [[(100, 2)]])
        self.assertIn("skipped_not_unread=1", "\n".join(captured.output))

    async def test_recheck_is_per_user_even_for_same_message(self):
        ntfy = FakeNtfy()
        database = FakeDatabase(
            [channel_candidate(target_user_id=2), channel_candidate(target_user_id=3)],
            still_unread={(100, 2)},
        )
        poller = self.make_poller(database, ntfy)

        self.assertEqual(await poller.scan_once(), (1, 0))
        self.assertEqual([call["user_id"] for call in ntfy.calls], [2])
        self.assertEqual(database.recheck_calls, [[(100, 2), (100, 3)]])

    async def test_recheck_failure_aborts_without_publishing(self):
        ntfy = FakeNtfy()
        database = FakeDatabase(
            [channel_candidate()],
            recheck_error=RuntimeError("database unavailable"),
        )
        poller = self.make_poller(database, ntfy)

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await poller.scan_once()
        self.assertEqual(ntfy.calls, [])

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
        self.assertEqual(poller.database.recheck_calls, [[(100, 2)]])

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
