# Security model

## Secrets

ntfy4zulip uses three sensitive credentials:

- `TOPIC_SECRET`: global HMAC key used to derive opaque per-user ntfy topics;
- `NTFY_AUTH_TOKEN`: write token for the ntfy bridge account;
- PostgreSQL credentials in `ZULIP_DB_DSN`.

The Zulip bot API key is stored in `zuliprc`.

None of these files/values should be committed. Back up `TOPIC_SECRET`: losing or
changing it changes every user's topic.

## PostgreSQL

Use a dedicated PostgreSQL role with SELECT-only access to the tables listed in
`sql/readonly_role.example.sql`. ntfy4zulip never needs to write to the Zulip
database.

Do not reuse Zulip's database owner/superuser credentials. At startup the application verifies effective SELECT access to every required table and rejects roles with INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, or public-schema CREATE privileges.

## ntfy topics

Topics are HMAC-derived capability secrets rather than predictable Zulip IDs. The
recommended ACL is documented in `docs/ntfy-acl.md`.

The stateless MVP has no per-user topic revocation. If an individual topic leaks,
there is no way to rotate just that user's topic without adding persistent mapping.
Rotating `TOPIC_SECRET` rotates all topics.

## Logs

The application logs message IDs and user IDs where useful for diagnostics, but does
not intentionally log:

- message bodies;
- full ntfy topics;
- `TOPIC_SECRET`;
- ntfy tokens;
- PostgreSQL passwords;
- Zulip API keys.

Run ntfy and Zulip over HTTPS in production.

## Reporting

This repository is private during initial development. Report discovered security
issues directly to the repository owner rather than publishing credentials or message
contents in an issue.
