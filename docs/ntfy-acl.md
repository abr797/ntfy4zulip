# Recommended ntfy ACL for ntfy4zulip

ntfy4zulip deliberately does not keep a `Zulip user_id -> ntfy credentials` database.
The recommended deployment therefore treats each high-entropy HMAC-derived topic as a
capability secret:

- anyone who knows a `zulip_*` topic may **read** it;
- anonymous users may **not publish** to it;
- the bridge account may **publish** to `zulip_*`, but may not subscribe/read;
- all unrelated topics remain denied by default.

This keeps onboarding stateless while preventing the unsafe legacy pattern of sharing
one employee account with read access to every topic.

## ntfy server configuration

Enable authentication and deny access by default:

```yaml
auth-file: "/var/lib/ntfy/user.db"
auth-default-access: "deny-all"
cache-file: "/var/lib/ntfy/cache.db"
cache-duration: "15m"
```

Use HTTPS in production.

Create the bridge user and ACL entries:

```bash
ntfy user add push_bridge_user
ntfy access push_bridge_user "zulip_*" write-only
ntfy access everyone "zulip_*" read-only
ntfy token add push_bridge_user
```

Put the generated token in `NTFY_AUTH_TOKEN`.

With these rules, a phone can subscribe to its opaque topic without separate ntfy
credentials, while anonymous clients cannot forge notifications.

## Security properties and limits

The topic name is effectively a password/capability. ntfy explicitly documents that
when ACLs do not identify individual subscribers, an unguessable topic name is the
secret protecting the subscription. ntfy4zulip derives 192 bits of HMAC output for the
topic token, so brute-force discovery is infeasible when `TOPIC_SECRET` is strong.

Do not:

- use `zulip_<numeric user id>`;
- grant a shared employee user read access to `*`;
- log full topic names;
- send topics over plain HTTP.

If one user's topic leaks, the MVP has no per-user rotation state. Rotating
`TOPIC_SECRET` changes topics for **all** users. Per-user revocation would require
introducing persisted mapping/state and is intentionally outside the stateless MVP.

References:

- ntfy access control: https://docs.ntfy.sh/config/#access-control
- ntfy topic-name security: https://docs.ntfy.sh/faq/#if-topic-names-are-public-could-i-not-just-brute-force-them
