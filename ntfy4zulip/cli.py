from __future__ import annotations

import argparse
import asyncio
import logging

from .app import run
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ntfy4zulip",
        description="Send ntfy notifications for unread Zulip messages.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate configuration and exit without connecting to Zulip/PostgreSQL/ntfy",
    )
    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    args = build_parser().parse_args()
    configure_logging()
    config = load_config()

    if args.check_config:
        logging.getLogger(__name__).info(
            "configuration OK: zulip=%s ntfy=%s topic_prefix=%s delay=%sm",
            config.zulip_site,
            config.ntfy_host,
            config.ntfy_topic_prefix,
            config.notification_delay_minutes,
        )
        return

    asyncio.run(run(config))
