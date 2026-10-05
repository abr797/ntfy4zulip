from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Any

from .ntfy import NtfyClient
from .topics import topic_for_user

logger = logging.getLogger(__name__)

_SEEN_DM_LIMIT = 10_000


class EnrollmentBot:
    def __init__(
        self,
        *,
        zuliprc_path: Path,
        ntfy: NtfyClient,
        ntfy_public_url: str | None,
        topic_secret: str,
        topic_prefix: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.zuliprc_path = zuliprc_path
        self.ntfy = ntfy
        self.ntfy_public_url = (
            ntfy_public_url.rstrip("/") if ntfy_public_url else None
        )
        self.topic_secret = topic_secret
        self.topic_prefix = topic_prefix
        self.loop = loop
        self.listener_client: Any = None
        self.sender_client: Any = None
        self.bot_email: str | None = None

        self._seen_dm_ids: set[int] = set()
        self._seen_dm_order: deque[int] = deque()
        self._seen_dm_lock = threading.Lock()

    @staticmethod
    def _is_one_to_one_dm(message: dict[str, Any]) -> bool:
        if message.get("type") not in {"private", "direct"}:
            return False
        recipients = message.get("display_recipient")
        return isinstance(recipients, list) and len(recipients) == 2

    def _remember_dm(self, message_id: int) -> bool:
        """Return False if this Zulip DM message was already handled."""
        with self._seen_dm_lock:
            if message_id in self._seen_dm_ids:
                return False

            if len(self._seen_dm_order) >= _SEEN_DM_LIMIT:
                oldest = self._seen_dm_order.popleft()
                self._seen_dm_ids.discard(oldest)

            self._seen_dm_order.append(message_id)
            self._seen_dm_ids.add(message_id)
            return True

    def process_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "message":
            return
        message = event.get("message") or {}
        if message.get("sender_email") == self.bot_email:
            return
        if not self._is_one_to_one_dm(message):
            return

        try:
            message_id = int(message["id"])
            user_id = int(message["sender_id"])
            sender_email = str(message["sender_email"])
        except (KeyError, TypeError, ValueError):
            logger.warning("ignored malformed Zulip DM event")
            return

        if not self._remember_dm(message_id):
            logger.warning(
                "duplicate enrollment DM ignored message=%s user=%s",
                message_id,
                user_id,
            )
            return

        logger.info(
            "enrollment DM accepted message=%s user=%s timestamp=%s",
            message_id,
            user_id,
            message.get("timestamp"),
        )

        future = asyncio.run_coroutine_threadsafe(
            self._handle_dm(
                message_id=message_id,
                user_id=user_id,
                sender_email=sender_email,
            ),
            self.loop,
        )

        def log_failure(done_future: Any) -> None:
            try:
                done_future.result()
            except Exception:
                logger.exception(
                    "failed to handle enrollment DM message=%s user=%s",
                    message_id,
                    user_id,
                )

        future.add_done_callback(log_failure)

    async def _handle_dm(
        self,
        *,
        message_id: int,
        user_id: int,
        sender_email: str,
    ) -> None:
        topic = topic_for_user(user_id, self.topic_secret, self.topic_prefix)
        test_ok = await self.ntfy.send(
            topic=topic,
            title="Zulip push · test",
            message="Тестовое уведомление ntfy4zulip. Если вы его видите, подписка работает.",
            priority=4,
            tags=("white_check_mark", "bell"),
            source="enrollment",
            message_id=message_id,
            user_id=user_id,
        )
        logger.info(
            "enrollment test publish completed message=%s user=%s sent=%s",
            message_id,
            user_id,
            test_ok,
        )

        if test_ok:
            status = "Тестовое уведомление уже отправлено."
        else:
            status = "Тестовое уведомление отправить не удалось. Напишите мне ещё раз позже."

        if self.ntfy_public_url:
            instruction = (
                "Привет! Push-уведомления для вашего аккаунта Zulip готовы.\n\n"
                "Чтобы подключить их в приложении ntfy:\n"
                "1. Добавьте новую подписку.\n"
                "2. Включите «Использовать другой сервер».\n"
                "3. В поле сервера вставьте адрес из следующего сообщения.\n"
                "4. В поле «Тема» (Topic) вставьте секретный токен из третьего сообщения.\n"
                "5. Сохраните подписку.\n\n"
                "Секретный токен никому не пересылайте: он даёт доступ к вашей подписке.\n\n"
                f"{status}\n\n"
                "После подключения вы будете получать уведомления о сообщениях Zulip, "
                "которые остаются непрочитанными примерно через 3 минуты."
            )
            reply_parts = (instruction, self.ntfy_public_url, topic)
        else:
            reply_parts = (
                "Привет! Персональная подписка создана, но публичный адрес ntfy "
                "пока не настроен. Подключить мобильный клиент сейчас нельзя. "
                f"{status}",
            )

        for part_number, content in enumerate(reply_parts, start=1):
            result = await asyncio.to_thread(
                self.sender_client.send_message,
                {"type": "private", "to": [sender_email], "content": content},
            )
            if isinstance(result, dict) and result.get("result") != "success":
                logger.error(
                    "enrollment reply failed message=%s user=%s part=%s/%s result=%s",
                    message_id,
                    user_id,
                    part_number,
                    len(reply_parts),
                    result.get("result"),
                )
            else:
                logger.info(
                    "enrollment reply sent message=%s user=%s part=%s/%s",
                    message_id,
                    user_id,
                    part_number,
                    len(reply_parts),
                )

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
