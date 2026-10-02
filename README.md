# ntfy4zulip: DB-backed unread notifications (Zulip Server 12.2)

A stateless external service for self-hosted Zulip Server 12.2 that sends unread-message notifications through self-hosted ntfy, without modifying Zulip Server or Zulip clients.

## Behavior

Once per minute, the service queries the Zulip PostgreSQL database for `UserMessage` rows whose messages were sent in the closed minute bucket approximately 3–4 minutes ago and whose `read` flag is still unset. Each `(message_id, user_id)` row is sent to that user's deterministic ntfy topic.

The service deliberately does **not** catch up after downtime and does **not** reconstruct missing `UserMessage` rows for `long_term_idle` users. It is intended to run as a single instance.

Covered by the same query:

- 1:1 direct messages;
- group direct messages;
- public and private channels;
- mentions and ordinary channel messages when a `UserMessage` exists.

No Zulip Server or client modifications are required. The poller is scoped to the organization (realm) of the configured bot, so another organization hosted by the same Zulip Server is not scanned.

## Why `UserMessage`

In Zulip Server 12.2, `zerver_usermessage` stores per-user state for a message. Bit 0 of `flags` is `read`, so the raw SQL unread predicate is:

```sql
(um.flags & 1) = 0
```

The implementation is pinned conceptually to Zulip Server 12.2; re-check the upstream model before supporting another major version.

References:

- https://github.com/zulip/zulip/blob/12.2/zerver/models/messages.py
- https://github.com/zulip/zulip/blob/12.2/docs/subsystems/sending-messages.md

## Stateless user topics

A topic is derived from a stable Zulip user ID and a server secret:

```text
HMAC-SHA256(TOPIC_SECRET, "zulip-user:<user_id>")
```

The numeric user ID is not exposed in the topic. The current token keeps 192 bits of HMAC output. `TOPIC_SECRET` must be backed up; changing it changes every user's topic.

## Onboarding bot

Any 1:1 DM to the configured Generic bot causes the bot to:

1. derive the sender's personal topic;
2. publish a test notification to it immediately;
3. reply in Zulip with the ntfy server address and topic.

Channel messages and group DMs to the bot are ignored. Repeating the DM returns the same topic and sends another test push, making the bot a simple self-service diagnostic endpoint. The bot can remain a normal Generic bot; organization-admin privileges are not required in DB-backed mode.

## Install

Python 3.11+ is supported.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
cp .env.example .env
cp zuliprc.example zuliprc
```

`ntfy4zulip` loads `.env` and the default `zuliprc` from the current working directory (systemd uses `/opt/ntfy4zulip`), or you can set `ZULIPRC_PATH` explicitly. Keep the bot's normal `zuliprc` there. At startup the service calls `GET /users/me` once to obtain the bot `user_id`; the DB query uses that ID only to determine the bot's realm.

Create a dedicated PostgreSQL account with **SELECT-only** privileges. See `sql/readonly_role.example.sql`. Startup fails fast if required SELECT privileges are missing or if that role has table-write/public-schema CREATE privileges.

Validate local configuration without connecting to any service:

```bash
ntfy4zulip --check-config
```

Run:

```bash
ntfy4zulip
```

`python3 run_db.py` remains as a compatibility entry point.

## ntfy ACL

The recommended stateless security model is:

```text
auth-default-access = deny-all
anonymous/everyone: zulip_* -> read-only
push_bridge_user:   zulip_* -> write-only
```

Thus a high-entropy topic is a capability secret: a phone needs only the topic to subscribe, anonymous users cannot publish forged notifications, and the bridge cannot read users' cached notifications.

Exact setup commands and security tradeoffs are in [docs/ntfy-acl.md](docs/ntfy-acl.md). If you change `NTFY_TOPIC_PREFIX`, change the ntfy ACL wildcard accordingly. Do **not** use the legacy pattern of one shared employee account with read access to all topics.

A short ntfy cache such as 15 minutes is suitable for this project: it lets the onboarding test push survive the few seconds before a user subscribes and tolerates brief phone disconnects without replaying hour-old notifications.

## Failure model

There is intentionally no Redis, local state database, watermark, persistent queue or catch-up.

- If the service is down during a minute bucket, those push notifications are missed.
- A failed PostgreSQL scan is logged; that bucket is lost and the next minute is still attempted.
- A failed ntfy publish is logged and not persistently retried.
- One malformed notification candidate does not block the rest of the bucket.
- On startup/restart, the poller waits for the next minute boundary rather than rescanning the current bucket.
- Running multiple copies will create duplicate pushes; deploy one instance.

These choices intentionally favor a simple timely-notification service over delayed recovery. The messages themselves remain in Zulip.

## Deep links

The link encoder follows Zulip Server 12.2 URL rules:

- channel: `#narrow/channel/<id-name>/topic/<topic>/near/<message_id>`
- DM: `#narrow/dm/<sorted-user-ids>[-group]/near/<message_id>`

Reference: https://github.com/zulip/zulip/blob/12.2/zerver/lib/url_encoding.py

## Demo without Zulip

Start the included mock ntfy server:

```bash
python testing/mock_ntfy_server.py
```

Then, in another shell:

```bash
TOPIC_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
NTFY_HOST=http://127.0.0.1:8081 \
ntfy4zulip-demo --user-id 42
```

This exercises topic derivation, notification formatting, deep-link generation and ntfy HTTP transport without Zulip or PostgreSQL.

## Tests

Unit tests:

```bash
python -m unittest discover -s tests -v
```

The GitHub Actions workflow additionally:

- executes the production SQL against a real PostgreSQL 16 service using synthetic Zulip-compatible tables;
- tests the closed 3–4 minute bucket and recipient filters;
- runs Ruff and `compileall`;
- builds wheel/sdist;
- verifies the installed CLI's offline config check.

The remaining real-environment validation is tracked in [docs/deployment-checklist.md](docs/deployment-checklist.md).

## Security and references

- [SECURITY.md](SECURITY.md)
- [ntfy ACL model](docs/ntfy-acl.md)
- [deployment validation checklist](docs/deployment-checklist.md)
- [references and prior art](docs/references.md)
