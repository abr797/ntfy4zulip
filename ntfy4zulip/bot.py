from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

from .ntfy import NtfyClient
from .topics import topic_for_user

logger = logging.getLogger(__name__)


class EnrollmentBot:
    def __init__(
        self,
        *,
        zuliprc_path: Path,
        ntfy: NtfyClient,
        ntfy_host: str,
        topic_secret: str,
        topic_prefix: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.zuliprc_path = zuliprc_path
        self.ntfy = ntfy
        self.ntfy_host = ntfy_host.rstrip("/")
        self.topic_secret = topic_secret
        self.topic_prefix = topic_prefix
        self.loop = loop
        self.listener_client: Any = None
        self.sender_client: Any = None
        self.bot_email: str | None = None

    @staticmethod
    def _is_one_to_one_dm(message: dict[str, Any]) -> bool:
        if message.get("type") not in {"private", "direct"}:
            return False
        recipients = message.get("display_recipient")
        return isinstance(recipients, list) and len(recipients) == 2

    def process_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "message":
            return
        message = event.get("message") or {}
        if message.get("sender_email") == self.bot_email:
            return
        if not self._is_one_to_one_dm(message):
            return

        try:
            user_id = int(message["sender_id"])
            sender_email = str(message["sender_email"])
        except (KeyError, TypeError, ValueError):
            logger.warning("ignored malformed Zulip DM event")
            return

        future = asyncio.run_coroutine_threadsafe(
            self._handle_dm(user_id=user_id, sender_email=sender_email),
            self.loop,
        )

        def log_failure(done_future: Any) -> None:
            try:
                done_future.result()
            except Exception:
                logger.exception("failed to handle enrollment DM")

        future.add_done_callback(log_failure)

    async def _handle_dm(self, *, user_id: int, sender_email: str) -> None:
        topic = topic_for_user(user_id, self.topic_secret, self.topic_prefix)
        test_ok = await self.ntfy.send(
            topic=topic,
            title="Zulip push · test",
            message="Тестовое уведомление ntfy4zulip. Если вы его видите, подписка работает.",
            priority=4,
            tags=("white_check_mark", "bell"),
        )

        if test_ok:
            status = "Я уже отправил в него тестовое уведомление."
        else:
            status = "Тестовое уведомление отправить не удалось. Напишите мне ещё раз позже."

        content = (
            "Привет! Push-уведомления для вашего аккаунта Zulip готовы.\n\n"
            f"**Сервер ntfy:** `{self.ntfy_host}`\n\n"
            f"**Ваш персональный topic:** `{topic}`\n\n"
            "Добавьте этот topic в приложение ntfy.\n\n"
            f"{status}\n\n"
            "После подключения вы будете получать уведомления о сообщениях Zulip, "
            "которые остаются непрочитанными примерно через 3 минуты."
        )
        result = await asyncio.to_thread(
            self.sender_client.send_message,
            {"type": "private", "to": [sender_email], "content": content},
        )
        if isinstance(result, dict) and result.get("result") != "success":
            logger.error("failed to send enrollment reply: %r", result)

    def _listen_forever(self) -> None:
        self.listener_client.call_on_each_event(callback=self.process_event, event_types=["message"])

    async def run(self, stop_event: asyncio.Event) -> None:
        import zulip

        self.listener_client = await asyncio.to_thread(
            zulip.Client, config_file=str(self.zuliprc_path)
        )
        self.sender_client = await asyncio.to_thread(
            zulip.Client, config_file=str(self.zuliprc_path)
        )
        self.bot_email = self.listener_client.email
        logger.info("enrollment bot authorized as %s", self.bot_email)

        listener_done: asyncio.Future[None] = self.loop.create_future()

        def set_listener_exception(exc: BaseException) -> None:
            if not listener_done.done():
                listener_done.set_exception(exc)

        def set_listener_result() -> None:
            if not listener_done.done():
                listener_done.set_result(None)

        def listener_target() -> None:
            try:
                self._listen_forever()
            except BaseException as exc:
                self.loop.call_soon_threadsafe(set_listener_exception, exc)
            else:
                self.loop.call_soon_threadsafe(set_listener_result)

        thread = threading.Thread(
            target=listener_target,
            name="ZulipEnrollmentListener",
            daemon=True,
        )
        thread.start()

        stop_waiter = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            {listener_done, stop_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if listener_done in done:
            exc = listener_done.exception()
            if exc is not None:
                raise exc
