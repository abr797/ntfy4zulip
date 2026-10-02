#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging

from ntfy4zulip.app import run
from ntfy4zulip.config import load_config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = load_config()
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
