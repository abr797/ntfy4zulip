import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ntfy4zulip.config import _base_dir, load_config


class ConfigTests(unittest.TestCase):
    def make_base(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        (base / "zuliprc").write_text(
            "[api]\nsite=https://zulip.example\nemail=bot@example.com\nkey=test\n",
            encoding="utf-8",
        )
        return base

    def valid_env(self) -> dict[str, str]:
        return {
            "TOPIC_SECRET": "x" * 32,
            "ZULIP_DB_DSN": "postgresql://reader@example/zulip",
        }

    def test_minimal_config(self):
        base = self.make_base()
        with patch.dict(os.environ, self.valid_env(), clear=True):
            config = load_config(base)
        self.assertEqual(config.zulip_site, "https://zulip.example")
        self.assertEqual(config.ntfy_topic_prefix, "zulip")
        self.assertEqual(config.zulip_db_schema, "public")
        self.assertEqual(config.poll_interval_seconds, 60)
        self.assertEqual(config.notification_delay_minutes, 3)
        self.assertEqual(config.db_timeout_seconds, 15)

    def test_missing_topic_secret_is_rejected(self):
        base = self.make_base()
        with patch.dict(os.environ, {"ZULIP_DB_DSN": "postgresql://test"}, clear=True):
            with self.assertRaisesRegex(ValueError, "TOPIC_SECRET"):
                load_config(base)

    def test_short_topic_secret_is_rejected(self):
        base = self.make_base()
        env = self.valid_env() | {"TOPIC_SECRET": "short"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "at least 32 bytes"):
                load_config(base)

    def test_non_minute_poll_interval_is_rejected(self):
        base = self.make_base()
        env = self.valid_env() | {"POLL_INTERVAL_SECONDS": "30"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "must be 60"):
                load_config(base)

    def test_custom_database_schema(self):
        base = self.make_base()
        env = self.valid_env() | {"ZULIP_DB_SCHEMA": "zulip"}
        with patch.dict(os.environ, env, clear=True):
            config = load_config(base)
        self.assertEqual(config.zulip_db_schema, "zulip")

    def test_invalid_database_schema_is_rejected(self):
        base = self.make_base()
        env = self.valid_env() | {"ZULIP_DB_SCHEMA": "zulip;drop schema public"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "ZULIP_DB_SCHEMA"):
                load_config(base)

    def test_invalid_ntfy_url_is_rejected(self):
        base = self.make_base()
        env = self.valid_env() | {"NTFY_HOST": "not-a-url"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "NTFY_HOST"):
                load_config(base)

    def test_invalid_zulip_site_is_rejected(self):
        base = self.make_base()
        (base / "zuliprc").write_text(
            "[api]\nsite=zulip.example\nemail=bot@example.com\nkey=test\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, self.valid_env(), clear=True):
            with self.assertRaisesRegex(ValueError, "Zulip site"):
                load_config(base)

    def test_default_base_dir_is_current_working_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("pathlib.Path.cwd", return_value=Path(temp)):
                self.assertEqual(_base_dir(), Path(temp))

    def test_invalid_database_timeout_is_rejected(self):
        base = self.make_base()
        env = self.valid_env() | {"DB_TIMEOUT_SECONDS": "0"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "DB_TIMEOUT_SECONDS"):
                load_config(base)

    def test_missing_zuliprc_is_rejected(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.dict(os.environ, self.valid_env(), clear=True):
            with self.assertRaises(FileNotFoundError):
                load_config(Path(temp.name))
