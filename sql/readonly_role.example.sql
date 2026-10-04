-- Run as a PostgreSQL administrator and replace password/database/schema as needed.
-- Production Zulip Docker deployments may use schema "zulip" rather than "public".
CREATE ROLE ntfy4zulip LOGIN PASSWORD 'CHANGE_ME'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS
    CONNECTION LIMIT 4;

ALTER ROLE ntfy4zulip SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE zulip TO ntfy4zulip;
GRANT USAGE ON SCHEMA zulip TO ntfy4zulip;
GRANT SELECT ON TABLE
    zulip.zerver_message,
    zulip.zerver_usermessage,
    zulip.zerver_userprofile,
    zulip.zerver_recipient,
    zulip.zerver_stream,
    zulip.zerver_subscription
TO ntfy4zulip;
