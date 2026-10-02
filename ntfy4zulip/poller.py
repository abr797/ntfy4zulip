from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .database import ZulipDatabase
from .links import candidate_message_url
from .messages import notification_text
from .ntfy import NtfyClient
from .topics import topic_for_user

logger = logging.getLogger(__name__)


class NotificationPoller:
    def __init__(
        self,
        *,
        database: ZulipDatabase,
        ntfy: NtfyClient,
        zulip_site: str,
        topic_secret: str,
        topic_prefix: str,
        preview_chars: int = 800,
        poll_interval_seconds: int = 60,
    ) -> None:
        self.database = database
        self.ntfy = ntfy
        self.zulip_site = zulip_site
        self.topic_secret = topic_secret
        self.topic_prefix = topic_prefix
        self.preview_chars = preview_chars
        self.poll_interval_seconds = poll_interval_seconds

    async def scan_once(self) -> tuple[int, int]:
        candidates = await asyncio.to_thread(self.database.fetch_candidates)
        logger.info("notification scan found %d unread candidates", len(candidates))

        seen: set[tuple[int, int]] = set()
        tasks: list[asyncio.Task[bool]] = []
        build_failures = 0

        for candidate in candidates:
            key = (candidate.message_id, candidate.target_user_id)
            if key in seen:
                logger.warning("duplicate candidate in same scan: message=%s user=%s", *key)
                continue
            seen.add(key)

            try:
                topic = topic_for_user(
                    candidate.target_user_id,
                    self.topic_secret,
                    self.topic_prefix,
                )
                title, message = notification_text(candidate, self.preview_chars)
                click = candidate_message_url(self.zulip_site, candidate)
            except Exception:
                build_failures += 1
                logger.exception(
                    "failed to build notification: message=%s user=%s",
                    candidate.message_id,
                    candidate.target_user_id,
                )
                continue

            tasks.append(
                asyncio.create_task(
                    self.ntfy.send(
                        topic=topic,
                        title=title,
                        message=message,
                        click=click,
                    )
                )
            )

        if not tasks:
            return 0, build_failures

        results = await asyncio.gather(*tasks)
        sent = sum(1 for result in results if result)
        failed = len(results) - sent + build_failures
        logger.info("notification scan completed sent=%d failed=%d", sent, failed)
        return sent, failed

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._seconds_until_next_tick(),
                )
                continue
            except asyncio.TimeoutError:
                pass

            try:
                await self.scan_once()
            except Exception:
                # Stateless failure semantics: this bucket is intentionally lost,
                # but the process stays alive and the next minute is still scanned.
                logger.exception("notification scan failed; bucket will not be retried")

    def _seconds_until_next_tick(self) -> float:
        now = datetime.now(timezone.utc)
        epoch = now.timestamp()
        interval = self.poll_interval_seconds
        next_epoch = (int(epoch) // interval + 1) * interval
        return max(0.1, next_epoch - epoch + 1.0)
