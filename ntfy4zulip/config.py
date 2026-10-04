from __future__ import annotations

import configparser
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    zulip_site: str
    zuliprc_path: Path
    zulip_db_dsn: str
    zulip_db_schema: str
    ntfy_host: str
    ntfy_auth_token: str | None
    ntfy_topic_prefix: str
    topic_secret: str
    notification_delay_minutes: int = 3
    poll_interval_seconds: int = 60
    ntfy_concurrency: int = 20
    ntfy_timeout_seconds: float = 10.0
    message_preview_chars: int = 800
    db_timeout_seconds: int = 15


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Installed console scripts must resolve .env/zuliprc relative to where the
    # service is launched, not relative to site-packages.
    return Path.cwd()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _db_schema(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(
            "ZULIP_DB_SCHEMA must be a simple PostgreSQL identifier "
            "(letters, digits and underscore)"
        )
    return value


def _http_url(name: str, value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute http(s) URL")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def load_config(base_dir: Path | None = None) -> Config:
    base_dir = (base_dir or _base_dir()).resolve()
    load_dotenv(base_dir / ".env")

    zuliprc_path = Path(os.getenv("ZULIPRC_PATH", str(base_dir / "zuliprc"))).expanduser()
    if not zuliprc_path.exists():
        raise FileNotFoundError(f"Zulip config not found: {zuliprc_path}")

    parser = configparser.ConfigParser()
    parser.read(zuliprc_path)
    if not parser.has_option("api", "site"):
        raise ValueError(f"Missing [api] site in {zuliprc_path}")

    zulip_site = _http_url("Zulip site", parser.get("api", "site"))
    topic_secret = _require_env("TOPIC_SECRET")
    if len(topic_secret.encode("utf-8")) < 32:
        raise ValueError("TOPIC_SECRET must contain at least 32 bytes")

    poll_interval_seconds = _positive_int("POLL_INTERVAL_SECONDS", 60)
    if poll_interval_seconds != 60:
        raise ValueError("POLL_INTERVAL_SECONDS must be 60 in stateless bucket mode")

    return Config(
        zulip_site=zulip_site,
        zuliprc_path=zuliprc_path,
        zulip_db_dsn=_require_env("ZULIP_DB_DSN"),
        zulip_db_schema=_db_schema(os.getenv("ZULIP_DB_SCHEMA", "public")),
        ntfy_host=_http_url("NTFY_HOST", os.getenv("NTFY_HOST", "https://ntfy.sh")),
        ntfy_auth_token=os.getenv("NTFY_AUTH_TOKEN", "").strip() or None,
        ntfy_topic_prefix=os.getenv("NTFY_TOPIC_PREFIX", "zulip").strip().strip("_-") or "zulip",
        topic_secret=topic_secret,
        notification_delay_minutes=_positive_int("NOTIFICATION_DELAY_MINUTES", 3),
        poll_interval_seconds=poll_interval_seconds,
        ntfy_concurrency=_positive_int("NTFY_CONCURRENCY", 20),
        ntfy_timeout_seconds=_positive_float("NTFY_TIMEOUT_SECONDS", 10.0),
        message_preview_chars=_positive_int("MESSAGE_PREVIEW_CHARS", 800),
        db_timeout_seconds=_positive_int("DB_TIMEOUT_SECONDS", 15),
    )
