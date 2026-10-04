from __future__ import annotations

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)


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

        async with self.semaphore:
            try:
                async with self.session.post(
                    self.host,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                ) as response:
                    if 200 <= response.status < 300:
                        return True
                    body = await response.text()
                    logger.error("ntfy returned status=%s body=%r", response.status, body[:500])
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.error("ntfy request failed: %s", exc)
        return False
