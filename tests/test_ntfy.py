import unittest

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
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class NtfyTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_publish_uses_root_url_and_auth(self):
        session = FakeSession()
        client = NtfyClient(
            session=session,
            host="https://ntfy.example/",
            auth_token="tk_test",
            concurrency=2,
            timeout_seconds=5,
        )
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
