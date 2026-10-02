-- Run as a PostgreSQL administrator and replace the password/role name.
CREATE ROLE ntfy4zulip LOGIN PASSWORD 'CHANGE_ME';
GRANT CONNECT ON DATABASE zulip TO ntfy4zulip;
GRANT USAGE ON SCHEMA public TO ntfy4zulip;
GRANT SELECT ON TABLE
    zerver_message,
    zerver_usermessage,
    zerver_userprofile,
    zerver_recipient,
    zerver_stream,
    zerver_subscription
TO ntfy4zulip;
