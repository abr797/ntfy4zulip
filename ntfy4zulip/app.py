from __future__ import annotations

import asyncio
import logging
import signal

import aiohttp

from .bot import EnrollmentBot
from .config import Config
from .database import ZulipDatabase
from .ntfy import NtfyClient
from .poller import NotificationPoller

logger = logging.getLogger(__name__)


async def _get_bot_user_id(zuliprc_path) -> int:
    import zulip

    client = await asyncio.to_thread(zulip.Client, config_file=str(zuliprc_path))
    profile = await asyncio.to_thread(client.get_profile)
    if not isinstance(profile, dict) or profile.get("result") != "success":
        raise RuntimeError(f"Could not get Zulip bot profile: {profile!r}")
    try:
        return int(profile["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Zulip bot profile has no valid user_id: {profile!r}") from exc


async def run(config: Config) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info("shutdown requested")
        stop_event.set()

    for signame in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signame, request_stop)
        except NotImplementedError:
            pass

    bot_user_id = await _get_bot_user_id(config.zuliprc_path)
    logger.info("scoping DB poller to realm of Zulip bot user_id=%s", bot_user_id)

    async with aiohttp.ClientSession() as session:
        ntfy = NtfyClient(
            session=session,
            host=config.ntfy_host,
            auth_token=config.ntfy_auth_token,
            concurrency=config.ntfy_concurrency,
            timeout_seconds=config.ntfy_timeout_seconds,
        )
        database = ZulipDatabase(
            dsn=config.zulip_db_dsn,
            realm_anchor_user_id=bot_user_id,
            delay_minutes=config.notification_delay_minutes,
            timeout_seconds=config.db_timeout_seconds,
            schema=config.zulip_db_schema,
        )
        db_user = await asyncio.to_thread(database.validate_access)
        logger.info("PostgreSQL access validated as read-only role=%s", db_user)

        poller = NotificationPoller(
            database=database,
            ntfy=ntfy,
            zulip_site=config.zulip_site,
            topic_secret=config.topic_secret,
            topic_prefix=config.ntfy_topic_prefix,
            preview_chars=config.message_preview_chars,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        bot = EnrollmentBot(
            zuliprc_path=config.zuliprc_path,
            ntfy=ntfy,
            ntfy_host=config.ntfy_host,
            topic_secret=config.topic_secret,
            topic_prefix=config.ntfy_topic_prefix,
            loop=loop,
        )

        tasks = {
            asyncio.create_task(poller.run(stop_event), name="notification-poller"),
            asyncio.create_task(bot.run(stop_event), name="enrollment-bot"),
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        fatal_error: BaseException | None = None

        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None:
                logger.error("task %s failed", task.get_name(), exc_info=exc)
                fatal_error = exc
                stop_event.set()
            elif not stop_event.is_set():
                fatal_error = RuntimeError(
                    f"task {task.get_name()} stopped unexpectedly without shutdown"
                )
                logger.error("%s", fatal_error)
                stop_event.set()

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        if fatal_error is not None:
            raise fatal_error
