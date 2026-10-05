from __future__ import annotations

import asyncio
import hashlib
import logging

import aiohttp

logger = logging.getLogger(__name__)


def _topic_fingerprint(topic: str) -> str:
    return hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]


class NtfyClient:
    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        host: str,
        auth_token: str | None,
        concurrency: int = 20,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.session = session
        self.host = host.rstrip("/")
        self.auth_token = auth_token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(concurrency)

    async def send(
        self,
        *,
        topic: str,
        title: str,
        message: str,
        click: str | None = None,
        priority: int = 4,
        tags: tuple[str, ...] = ("speech_balloon", "bell"),
        source: str = "unspecified",
        message_id: int | None = None,
        user_id: int | None = None,
    ) -> bool:
        payload: dict[str, object] = {
            "topic": topic,
            "title": title,
            "message": message,
            "priority": priority,
            "tags": list(tags),
            "markdown": True,
        }
        if click:
            payload["click"] = click

        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        topic_fp = _topic_fingerprint(topic)

        async with self.semaphore:
            try:
                async with self.session.post(
                    self.host,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                ) as response:
                    if 200 <= response.status < 300:
                        logger.info(
                            "ntfy publish succeeded status=%s source=%s "
                            "message=%s user=%s topic_fp=%s",
                            response.status,
                            source,
                            message_id,
                            user_id,
                            topic_fp,
                        )
                        return True
                    body = await response.text()
                    logger.error(
                        "ntfy publish failed status=%s source=%s message=%s "
                        "user=%s topic_fp=%s body=%r",
                        response.status,
                        source,
                        message_id,
                        user_id,
                        topic_fp,
                        body[:500],
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.error(
                    "ntfy request failed source=%s message=%s user=%s "
                    "topic_fp=%s error=%s",
                    source,
                    message_id,
                    user_id,
                    topic_fp,
                    exc,
                )
        return False
