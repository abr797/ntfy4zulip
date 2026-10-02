import re
import unittest

from ntfy4zulip.topics import topic_for_user


class TopicTests(unittest.TestCase):
    def test_topic_is_stable(self):
        self.assertEqual(
            topic_for_user(42, "x" * 32, "corp"),
            topic_for_user(42, "x" * 32, "corp"),
        )

    def test_different_users_get_different_topics(self):
        self.assertNotEqual(
            topic_for_user(42, "x" * 32),
            topic_for_user(43, "x" * 32),
        )

    def test_different_secrets_get_different_topics(self):
        self.assertNotEqual(
            topic_for_user(42, "x" * 32),
            topic_for_user(42, "y" * 32),
        )

    def test_topic_does_not_expose_user_id(self):
        topic = topic_for_user(424242, "x" * 32)
        self.assertNotIn("424242", topic)
        self.assertRegex(topic, re.compile(r"^[A-Za-z0-9_-]+$"))

    def test_invalid_prefix_rejected(self):
        with self.assertRaises(ValueError):
            topic_for_user(42, "x" * 32, "not/a/topic")
