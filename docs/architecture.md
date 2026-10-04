# MVP architecture

ntfy4zulip has two independent inputs and one shared ntfy transport.

```text
                        +----------------------+
                        |   self-hosted Zulip  |
                        +----------+-----------+
                                   |
                 +-----------------+------------------+
                 |                                    |
        read-only PostgreSQL                    Generic bot API
                 |                                    |
                 v                                    v
        minute-bucket poller                 1:1 enrollment listener
                 |                                    |
                 | target user_id                     | sender_id
                 +------------------+-----------------+
                                    |
                                    v
                       HMAC topic_for_user(user_id)
                                    |
                                    v
                            async ntfy client
                                    |
                                    v
                         self-hosted ntfy server
```

## Notification path

At each minute boundary the poller asks PostgreSQL for the single closed one-minute
bucket whose messages are approximately 3–4 minutes old.

Eligibility is intentionally simple:

```text
UserMessage exists
AND read bit is not set
AND target is active human
AND target != sender
AND message belongs to the bot's realm
```

The result row already identifies the per-user recipient. No channel subscriber
lookup is required.

There is no state between scans. Missing scans are not replayed.

## Enrollment path

Any 1:1 DM to the Generic bot is treated as an enrollment/diagnostic request:

1. use the event's stable `sender_id`;
2. derive the same HMAC topic used by the poller;
3. send a test push immediately;
4. reply with server + topic + instructions.

The bot does not need organization-admin permissions because it does not monitor
organization traffic. The separate PostgreSQL account handles read-only notification
discovery.

## State

Persistent application state: **none**.

Persistent secrets/configuration:

- `TOPIC_SECRET`;
- Zulip bot `zuliprc`;
- PostgreSQL read-only DSN;
- ntfy bridge write token.

## Deliberate constraints

- one service instance;
- no catch-up;
- no Redis/queue;
- no online/offline tracking;
- no native Zulip notification-preference emulation;
- no long-term-idle reconstruction when Zulip has no `UserMessage`;
- no individual topic rotation without future persistent state.
