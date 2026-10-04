import unittest
from datetime import datetime, timezone

from ntfy4zulip.links import candidate_message_url, encode_hash_component
from ntfy4zulip.models import NotificationCandidate


def candidate(**overrides):
    values = dict(
        message_id=556,
        date_sent=datetime.now(timezone.utc),
        sender_id=10,
        sender_full_name="King Hamlet",
        target_user_id=12,
        target_full_name="Othello",
        content="hello",
        topic_name="normal topic",
        is_channel_message=True,
        stream_id=3,
        stream_name="Verona",
        dm_user_ids=(),
    )
    values.update(overrides)
    return NotificationCandidate(**values)


class LinkTests(unittest.TestCase):
    def test_hash_encoding_matches_zulip_style(self):
        self.assertEqual(encode_hash_component("normal topic"), "normal.20topic")
        self.assertEqual(encode_hash_component("a.b"), "a.2Eb")

    def test_channel_message_link(self):
        url = candidate_message_url("https://chat.example", candidate())
        self.assertEqual(
            url,
            "https://chat.example/#narrow/channel/3-Verona/topic/normal.20topic/near/556",
        )

    def test_one_to_one_dm_link(self):
        c = candidate(is_channel_message=False, stream_id=None, stream_name=None, dm_user_ids=(12, 10))
        self.assertEqual(
            candidate_message_url("https://chat.example", c),
            "https://chat.example/#narrow/dm/10,12/near/556",
        )

    def test_group_dm_link(self):
        c = candidate(
            is_channel_message=False,
            stream_id=None,
            stream_name=None,
            dm_user_ids=(15, 10, 12),
        )
        self.assertEqual(
            candidate_message_url("https://chat.example", c),
            "https://chat.example/#narrow/dm/10,12,15-group/near/556",
        )
