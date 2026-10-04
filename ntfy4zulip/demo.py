from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

import aiohttp

from .links import candidate_message_url
from .messages import notification_text
from .models import NotificationCandidate
from .ntfy import NtfyClient
from .topics import topic_for_user


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ntfy4zulip-demo",
        description="Send a synthetic notification through ntfy without Zulip/PostgreSQL.",
    )
    parser.add_argument("--user-id", type=int, default=42)
    parser.add_argument(
        "--ntfy-publish-url",
        "--ntfy-host",
        dest="ntfy_publish_url",
        default=(
            os.getenv("NTFY_PUBLISH_URL")
            or os.getenv("NTFY_HOST")
            or "http://127.0.0.1:8081"
        ),
    )
    parser.add_argument("--ntfy-token", default=os.getenv("NTFY_AUTH_TOKEN") or None)
    parser.add_argument("--topic-prefix", default=os.getenv("NTFY_TOPIC_PREFIX", "zulip"))
    parser.add_argument("--topic-secret", default=os.getenv("TOPIC_SECRET"))
    parser.add_argument("--zulip-site", default="https://zulip.example")
    return parser


async def send_demo(args: argparse.Namespace) -> bool:
    if not args.topic_secret or len(args.topic_secret.encode("utf-8")) < 32:
        raise SystemExit("TOPIC_SECRET/--topic-secret must contain at least 32 bytes")

    candidate = NotificationCandidate(
        message_id=123456,
        date_sent=datetime.now(timezone.utc),
        sender_id=1,
        sender_full_name="ntfy4zulip demo",
        target_user_id=args.user_id,
        target_full_name="Demo recipient",
        content="Synthetic notification: formatting, HMAC topic and ntfy transport are working.",
        topic_name="smoke test",
        is_channel_message=True,
        stream_id=1,
        stream_name="ntfy4zulip",
        dm_user_ids=(),
    )
    topic = topic_for_user(args.user_id, args.topic_secret, args.topic_prefix)
    title, message = notification_text(candidate, 800)
    click = candidate_message_url(args.zulip_site, candidate)

    async with aiohttp.ClientSession() as session:
        ntfy = NtfyClient(
            session=session,
            host=args.ntfy_publish_url,
            auth_token=args.ntfy_token,
        )
        ok = await ntfy.send(topic=topic, title=title, message=message, click=click)

    print(f"topic={topic}")
    print("result=sent" if ok else "result=failed")
    return ok


def main() -> None:
    args = build_parser().parse_args()
    ok = asyncio.run(send_demo(args))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
