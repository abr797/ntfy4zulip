from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .database import ZulipDatabase
from .messages import notification_text
from .models import NotificationCandidate
from .ntfy import NtfyClient
from .topics import topic_for_user

logger = logging.getLogger(__name__)

# Zulip Server 12.2: AbstractUserMessage.ALL_FLAGS indexes 3..6.
_DIRECT_MENTION_MASK = (1 << 3) | (1 << 6)  # @user and @group
_WILDCARD_MENTION_MASK = (1 << 4) | (1 << 5)  # @all / @everyone


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
        default_priority: int = 2,
        mention_priority: int = 4,
        wildcard_mention_priority: int = 3,
        dm_priority: int = 4,
        group_dm_priority: int = 3,
        folder_priorities: dict[str, int] | None = None,
    ) -> None:
        self.database = database
        self.ntfy = ntfy
        self.zulip_site = zulip_site
        self.topic_secret = topic_secret
        self.topic_prefix = topic_prefix
        self.preview_chars = preview_chars
        self.poll_interval_seconds = poll_interval_seconds
        self.default_priority = default_priority
        self.mention_priority = mention_priority
        self.wildcard_mention_priority = wildcard_mention_priority
        self.dm_priority = dm_priority
        self.group_dm_priority = group_dm_priority
        self.folder_priorities = {
            name.strip().casefold(): priority
            for name, priority in (folder_priorities or {}).items()
        }

    def priority_for_candidate(self, candidate: NotificationCandidate) -> int:
        """Classify notification first; folder priority can only raise it."""
        if not candidate.is_channel_message:
            # An incomplete recipient list should not silently downgrade a DM.
            return self.group_dm_priority if len(candidate.dm_user_ids) > 2 else self.dm_priority

        flags = candidate.user_message_flags
        if flags & _DIRECT_MENTION_MASK:
            priority = self.mention_priority
            if flags & _WILDCARD_MENTION_MASK:
                priority = max(priority, self.wildcard_mention_priority)
        elif flags & _WILDCARD_MENTION_MASK:
            priority = self.wildcard_mention_priority
        else:
            priority = self.default_priority

        if candidate.folder_name:
            folder_priority = self.folder_priorities.get(
                candidate.folder_name.strip().casefold()
            )
            if folder_priority is not None:
                priority = max(priority, folder_priority)
        return priority

    async def scan_once(self) -> tuple[int, int]:
        candidates = await asyncio.to_thread(self.database.fetch_candidates)
        logger.info("notification scan found %d unread candidates", len(candidates))

        seen: set[tuple[int, int]] = set()
        prepared: list[tuple[tuple[int, int], str, str, str, int]] = []
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
                priority = self.priority_for_candidate(candidate)
            except Exception:
                build_failures += 1
                logger.exception(
                    "failed to build notification: message=%s user=%s",
                    candidate.message_id,
                    candidate.target_user_id,
                )
                continue

            prepared.append((key, topic, title, message, priority))

        if not prepared:
            if build_failures:
                logger.info(
                    "notification scan completed sent=0 skipped_not_unread=0 failed=%d",
                    build_failures,
                )
            return 0, build_failures

        # No publish tasks start until a second read-only SQL query succeeds.
        # Failure is fatal for this scan: never send with unverified read state.
        still_unread = await asyncio.to_thread(
            self.database.recheck_unread,
            [key for key, _, _, _, _ in prepared],
        )

        tasks: list[asyncio.Task[bool]] = []
        skipped_not_unread = 0
        for key, topic, title, message, priority in prepared:
            if key not in still_unread:
                skipped_not_unread += 1
                logger.info(
                    "notification skipped no_longer_unread message=%s user=%s",
                    *key,
                )
                continue

            tasks.append(
                asyncio.create_task(
                    self.ntfy.send(
                        topic=topic,
                        title=title,
                        message=message,
                        priority=priority,
                        source="poller",
                        message_id=key[0],
                        user_id=key[1],
                    )
                )
            )

        results = await asyncio.gather(*tasks)
        sent = sum(1 for result in results if result)
        failed = len(results) - sent + build_failures
        logger.info(
            "notification scan completed sent=%d skipped_not_unread=%d failed=%d",
            sent,
            skipped_not_unread,
            failed,
        )
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
