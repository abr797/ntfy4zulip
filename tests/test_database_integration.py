import os
import unittest

from ntfy4zulip.database import ZulipDatabase

DSN = os.getenv("TEST_POSTGRES_DSN")
READONLY_DSN = os.getenv("TEST_READONLY_POSTGRES_DSN")


@unittest.skipUnless(DSN, "TEST_POSTGRES_DSN is not set")
class DatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.conn = psycopg.connect(DSN, autocommit=True)
        cur = cls.conn.cursor()

        for table in (
            "zerver_subscription",
            "zerver_usermessage",
            "zerver_message",
            "zerver_stream",
            "zerver_recipient",
            "zerver_userprofile",
        ):
            cur.execute(f"DROP TABLE IF EXISTS {table}")

        cur.execute(
            """
            CREATE TABLE zerver_userprofile (
                id BIGINT PRIMARY KEY,
                realm_id BIGINT NOT NULL,
                full_name TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_bot BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE zerver_recipient (
                id BIGINT PRIMARY KEY,
                type SMALLINT NOT NULL,
                type_id BIGINT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE zerver_stream (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE zerver_message (
                id BIGINT PRIMARY KEY,
                date_sent TIMESTAMPTZ NOT NULL,
                sender_id BIGINT NOT NULL,
                recipient_id BIGINT NOT NULL,
                realm_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                is_channel_message BOOLEAN NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE zerver_usermessage (
                user_profile_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                flags INTEGER NOT NULL,
                PRIMARY KEY (user_profile_id, message_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE zerver_subscription (
                id BIGSERIAL PRIMARY KEY,
                user_profile_id BIGINT NOT NULL,
                recipient_id BIGINT NOT NULL
            )
            """
        )

        cur.execute(
            """
            INSERT INTO zerver_userprofile
                (id, realm_id, full_name, is_active, is_bot)
            VALUES
                (1,   1, 'Alice', TRUE, FALSE),
                (2,   1, 'Bob', TRUE, FALSE),
                (3,   1, 'Carol', TRUE, FALSE),
                (4,   1, 'Another bot', TRUE, TRUE),
                (5,   1, 'Inactive user', FALSE, FALSE),
                (6,   2, 'Other realm sender', TRUE, FALSE),
                (7,   2, 'Other realm target', TRUE, FALSE),
                (900, 1, 'Enrollment bot', TRUE, TRUE)
            """
        )
        cur.execute(
            """
            INSERT INTO zerver_stream (id, name)
            VALUES (10, 'development'), (20, 'other realm')
            """
        )
        cur.execute(
            """
            INSERT INTO zerver_recipient (id, type, type_id)
            VALUES
                (100, 2, 10),
                (101, 3, 1001),
                (102, 3, 1002),
                (200, 2, 20)
            """
        )
        cur.execute(
            """
            INSERT INTO zerver_subscription (user_profile_id, recipient_id)
            VALUES
                (1, 101), (2, 101),
                (1, 102), (2, 102), (3, 102)
            """
        )

        cur.execute(
            """
            INSERT INTO zerver_message
                (id, date_sent, sender_id, recipient_id, realm_id,
                 subject, content, is_channel_message)
            VALUES
                (1001, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 100, 1, 'backend', 'eligible channel', TRUE),
                (1002, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 100, 1, 'backend', 'already read', TRUE),
                (1003, date_trunc('minute', CURRENT_TIMESTAMP) - interval '2 minutes 30 seconds',
                 1, 100, 1, 'backend', 'too new', TRUE),
                (1004, date_trunc('minute', CURRENT_TIMESTAMP) - interval '4 minutes 30 seconds',
                 1, 100, 1, 'backend', 'too old', TRUE),
                (1005, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 101, 1, '', 'eligible one-to-one DM', FALSE),
                (1006, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 102, 1, '', 'eligible group DM', FALSE),
                (1007, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 100, 1, 'backend', 'target is a bot', TRUE),
                (1008, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 1, 100, 1, 'backend', 'target inactive', TRUE),
                (1009, date_trunc('minute', CURRENT_TIMESTAMP) - interval '3 minutes 30 seconds',
                 6, 200, 2, 'other', 'other realm', TRUE)
            """
        )
        cur.execute(
            """
            INSERT INTO zerver_usermessage (user_profile_id, message_id, flags)
            VALUES
                (1, 1001, 0),
                (2, 1001, 0),
                (2, 1002, 1),
                (2, 1003, 0),
                (2, 1004, 0),
                (2, 1005, 0),
                (2, 1006, 0),
                (3, 1006, 0),
                (4, 1007, 0),
                (5, 1008, 0),
                (7, 1009, 0)
            """
        )

        if READONLY_DSN:
            cur.execute("DROP ROLE IF EXISTS ntfy4zulip_reader_test")
            cur.execute(
                "CREATE ROLE ntfy4zulip_reader_test LOGIN PASSWORD 'reader-test-password'"
            )
            cur.execute("GRANT CONNECT ON DATABASE ntfy4zulip_test TO ntfy4zulip_reader_test")
            cur.execute("GRANT USAGE ON SCHEMA public TO ntfy4zulip_reader_test")
            cur.execute(
                """
                GRANT SELECT ON TABLE
                    zerver_message,
                    zerver_usermessage,
                    zerver_userprofile,
                    zerver_recipient,
                    zerver_stream,
                    zerver_subscription
                TO ntfy4zulip_reader_test
                """
            )
        cur.close()

    @classmethod
    def tearDownClass(cls):
        cur = cls.conn.cursor()
        for table in (
            "zerver_subscription",
            "zerver_usermessage",
            "zerver_message",
            "zerver_stream",
            "zerver_recipient",
            "zerver_userprofile",
        ):
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        if READONLY_DSN:
            cur.execute("DROP ROLE IF EXISTS ntfy4zulip_reader_test")
        cur.close()
        cls.conn.close()

    def assert_candidate_set(self, candidates):
        pairs = {(item.message_id, item.target_user_id) for item in candidates}
        self.assertEqual(
            pairs,
            {(1001, 2), (1005, 2), (1006, 2), (1006, 3)},
        )

        channel = next(item for item in candidates if item.message_id == 1001)
        self.assertTrue(channel.is_channel_message)
        self.assertEqual(channel.stream_id, 10)
        self.assertEqual(channel.stream_name, "development")

        dm = next(item for item in candidates if item.message_id == 1005)
        self.assertFalse(dm.is_channel_message)
        self.assertEqual(dm.dm_user_ids, (1, 2))

        group_dm = next(
            item
            for item in candidates
            if item.message_id == 1006 and item.target_user_id == 2
        )
        self.assertEqual(group_dm.dm_user_ids, (1, 2, 3))

    def test_real_postgresql_query_filters_and_maps_candidates(self):
        db = ZulipDatabase(DSN, realm_anchor_user_id=900, delay_minutes=3)
        self.assert_candidate_set(db.fetch_candidates())

    @unittest.skipUnless(READONLY_DSN, "TEST_READONLY_POSTGRES_DSN is not set")
    def test_select_only_role_can_run_poller_query_but_cannot_write(self):
        import psycopg
        from psycopg.errors import InsufficientPrivilege

        db = ZulipDatabase(READONLY_DSN, realm_anchor_user_id=900, delay_minutes=3)
        self.assert_candidate_set(db.fetch_candidates())

        with psycopg.connect(READONLY_DSN) as conn:
            with self.assertRaises(InsufficientPrivilege):
                conn.execute(
                    """
                    INSERT INTO zerver_userprofile
                        (id, realm_id, full_name, is_active, is_bot)
                    VALUES (9999, 1, 'should fail', TRUE, FALSE)
                    """
                )
