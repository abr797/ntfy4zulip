# ntfy4zulip: DB-backed unread notifications (Zulip Server 12.2)

A stateless external service for self-hosted Zulip Server 12.2 that sends unread-message notifications through a self-hosted ntfy server, without modifying Zulip Server or Zulip clients.

## Behavior

Once per minute, the service queries the Zulip PostgreSQL database for `UserMessage` rows whose messages were sent in the closed minute bucket approximately 3–4 minutes ago and whose `read` flag is still unset. Each `(message_id, user_id)` row is sent to that user's deterministic ntfy topic.

The service deliberately does **not** catch up after downtime and does **not** reconstruct missing `UserMessage` rows for `long_term_idle` users. It is intended to run as a single instance.

Covered by the same query:

- 1:1 direct messages;
- group direct messages;
- public channels;
- private channels;
- mentions and ordinary channel messages when a `UserMessage` exists.

No Zulip Server or client modifications are required. The poller is scoped to the organization (realm) of the configured bot, so another organization hosted by the same Zulip Server is not scanned.

## Why `UserMessage`

In Zulip Server 12.2, `zerver_usermessage` stores per-user state for a message. Bit 0 of `flags` is `read`, so the raw SQL unread predicate is:

```sql
(um.flags & 1) = 0
```

Reference: https://github.com/zulip/zulip/blob/12.2/zerver/models/messages.py

Soft-deactivation background: https://github.com/zulip/zulip/blob/12.2/docs/subsystems/sending-messages.md

## Stateless user topics

A topic is derived from a stable Zulip user ID and a server secret:

```text
HMAC-SHA256(TOPIC_SECRET, "zulip-user:<user_id>")
```

The user ID itself is not exposed in the topic. `TOPIC_SECRET` must be backed up; changing it changes every user's topic.

## Onboarding bot

Any 1:1 DM to the configured Generic bot causes the bot to:

1. derive the sender's personal topic;
2. publish a test notification to it immediately;
3. reply in Zulip with the ntfy server address and topic.

Channel messages and group DMs to the bot are ignored.

## Install

Copy the example configuration and install dependencies:

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Keep the bot's normal `zuliprc` in the project directory or set `ZULIPRC_PATH`. At startup the service calls `GET /users/me` once to obtain the bot `user_id`; the DB query uses that ID only to determine the bot's realm and scope notifications to that organization.

Create a dedicated PostgreSQL account with **SELECT-only** privileges. See `sql/readonly_role.example.sql`.

Run:

```bash
python3 run_db.py
```

## ntfy publishing

The client uses ntfy JSON publishing to avoid Unicode problems in HTTP headers. The payload is POSTed to the ntfy server root with fields such as `topic`, `title`, `message`, `click`, `priority`, and `tags`.

Reference: https://docs.ntfy.sh/publish/

For this mode, a short ntfy server cache (for example `cache-duration: "15m"`) is preferable to the default 12 hours: it lets the onboarding test push survive the few seconds before a user subscribes and tolerates brief phone disconnects, while avoiding hour-old notification replay. This is transport-level caching only; ntfy4zulip itself still performs no catch-up.

## Failure model

There is intentionally no Redis, local state database, watermark, or persistent retry queue.

- If the service is down during a minute bucket, those push notifications are missed.
- If an ntfy publish fails, the message remains safely available in Zulip; the push can be lost.
- On startup/restart, the poller waits for the next minute boundary rather than rescanning the current bucket. This intentionally favors a missed notification over a duplicate notification.
- Running multiple copies will create duplicate pushes; deploy one instance.
- ntfy read authentication/ACL is external to this service; users still need whatever credentials your ntfy server requires for subscribing to their topic.

## Deep links

The link encoder follows Zulip Server 12.2 URL rules:

- channel: `#narrow/channel/<id-name>/topic/<topic>/near/<message_id>`
- DM: `#narrow/dm/<sorted-user-ids>[-group]/near/<message_id>`

Reference: https://github.com/zulip/zulip/blob/12.2/zerver/lib/url_encoding.py

## Tests

Pure unit tests do not require a running Zulip server or PostgreSQL:

```bash
python3 -m unittest discover -s tests -v
```

Before production rollout, validate `sql/unread_notifications.sql` against the actual Zulip 12.2 database with a read-only role.
