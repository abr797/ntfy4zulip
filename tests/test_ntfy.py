import asyncio
import unittest

import aiohttp

from ntfy4zulip.ntfy import NtfyClient


class FakeResponse:
    def __init__(self, status=200, body="ok"):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._body


class FakeSession:
    def __init__(self, *, status=200, error=None):
        self.calls = []
        self.status = status
        self.error = error

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return FakeResponse(status=self.status)


class NtfyTests(unittest.IsolatedAsyncioTestCase):
    async def make_client(self, session):
        return NtfyClient(
            session=session,
            host="https://ntfy.example/",
            auth_token="tk_test",
            concurrency=2,
            timeout_seconds=5,
        )

    async def test_json_publish_uses_root_url_and_auth(self):
        session = FakeSession()
        client = await self.make_client(session)
        ok = await client.send(
            topic="zulip_abc",
            title="Привет",
            message="Тест",
            click="https://chat.example/#narrow/dm/1,2/near/3",
        )
        self.assertTrue(ok)
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://ntfy.example")
        self.assertEqual(kwargs["json"]["topic"], "zulip_abc")
        self.assertEqual(kwargs["json"]["title"], "Привет")
        self.assertTrue(kwargs["json"]["markdown"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tk_test")

    async def test_http_500_returns_false(self):
        client = await self.make_client(FakeSession(status=500))
        self.assertFalse(
            await client.send(topic="zulip_abc", title="test", message="test")
        )

    async def test_client_error_returns_false(self):
        client = await self.make_client(FakeSession(error=aiohttp.ClientError("offline")))
        self.assertFalse(
            await client.send(topic="zulip_abc", title="test", message="test")
        )

    async def test_timeout_returns_false(self):
        client = await self.make_client(FakeSession(error=asyncio.TimeoutError()))
        self.assertFalse(
            await client.send(topic="zulip_abc", title="test", message="test")
        )
