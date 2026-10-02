import asyncio
import unittest
from pathlib import Path

from ntfy4zulip.bot import EnrollmentBot


class FakeNtfy:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeZulipClient:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(message)
        return {"result": "success"}


class BotTests(unittest.IsolatedAsyncioTestCase):
    def test_only_one_to_one_dm_is_accepted(self):
        direct = {"type": "private", "display_recipient": [{"id": 1}, {"id": 2}]}
        group = {"type": "private", "display_recipient": [{"id": 1}, {"id": 2}, {"id": 3}]}
        stream = {"type": "stream", "display_recipient": "general"}
        self.assertTrue(EnrollmentBot._is_one_to_one_dm(direct))
        self.assertFalse(EnrollmentBot._is_one_to_one_dm(group))
        self.assertFalse(EnrollmentBot._is_one_to_one_dm(stream))

    async def test_dm_sends_test_push_and_instruction(self):
        ntfy = FakeNtfy()
        bot = EnrollmentBot(
            zuliprc_path=Path("zuliprc"),
            ntfy=ntfy,
            ntfy_host="https://ntfy.example",
            topic_secret="x" * 32,
            topic_prefix="zulip",
            loop=asyncio.get_running_loop(),
        )
        client = FakeZulipClient()
        bot.sender_client = client

        await bot._handle_dm(user_id=42, sender_email="bob@example.com")

        self.assertEqual(len(ntfy.calls), 1)
        topic = ntfy.calls[0]["topic"]
        self.assertTrue(topic.startswith("zulip_"))
        self.assertEqual(client.messages[0]["to"], ["bob@example.com"])
        self.assertIn(topic, client.messages[0]["content"])
