# Deployment validation checklist

Everything above the "real installation" boundary can be checked in CI without access
to a production Zulip server.

## Automated / synthetic validation

- [x] HMAC topics are deterministic and do not expose numeric Zulip user IDs.
- [x] Zulip 12.2-style channel and DM deep links have unit tests.
- [x] Notification formatting/truncation has unit tests.
- [x] ntfy JSON publishing has success, HTTP error, network error and timeout tests.
- [x] Enrollment bot happy/failure paths have unit tests.
- [x] Internal ntfy publishing and optional public client URL are independent.
- [x] Enrollment without a public URL still sends a test push and never exposes the internal publish URL.
- [x] Legacy `NTFY_HOST` remains backward compatible.
- [x] Configuration validation has unit tests.
- [x] Poller survives a failed PostgreSQL scan and continues to the next bucket.
- [x] One malformed candidate does not prevent delivery of other candidates.
- [x] Poller exits cleanly when its stop event is set.
- [x] The actual production SQL executes against PostgreSQL 16 in CI.
- [x] CI creates a separate SELECT-only PostgreSQL login, runs the production poller against a non-public `zulip` schema, and proves INSERT is denied.
- [x] The application sets a transaction-local search path to `ZULIP_DB_SCHEMA` and validates USAGE/CREATE on that actual schema.
- [x] An unrelated writable `public` schema does not force a global ACL change.
- [x] Startup privilege validation accepts the SELECT-only role and rejects a write-capable role or unknown bot user.
- [x] PostgreSQL connect/statement duration is bounded by configuration.
- [x] Synthetic SQL fixtures cover read/unread, sender exclusion, age window,
      active/bot filtering, realm isolation, 1:1 DM, group DM and channel metadata.
- [x] Python package builds as wheel/sdist.
- [x] Installed CLI performs an offline configuration check.
- [x] Ruff/compile checks run in CI.
- [x] A standalone demo can test HMAC + formatting + ntfy transport without Zulip.

## Real installation boundary

These are intentionally the only remaining validation steps that require the actual
environment:

- [ ] Run `sql/unread_notifications.sql` read-only against the real Zulip Server
      12.2 database and compare a few rows with the Zulip UI.
- [ ] Set `ZULIP_DB_SCHEMA` to the schema containing the Zulip tables and confirm the PostgreSQL role passes startup validation without changing unrelated `public` ACLs.
- [ ] Confirm the production PostgreSQL role cannot write to Zulip tables or CREATE in the configured Zulip schema.
- [ ] Send a 1:1 DM to the real enrollment bot and receive its instruction reply.
- [ ] Confirm local publishing works through `NTFY_PUBLISH_URL` on the Docker network without external DNS.
- [ ] When a public endpoint exists, set `NTFY_PUBLIC_URL`, subscribe a real ntfy phone/client to the returned topic, and receive the test push.
- [ ] Verify a channel message read within 3 minutes produces no push.
- [ ] Verify an unread channel message produces one push around 3–4 minutes later.
- [ ] Verify an unread 1:1 DM produces a push.
- [ ] Verify an unread group DM produces a push for each unread recipient except sender.
- [ ] Verify private-channel messages follow the same behavior.
- [ ] Stop the service for a bucket and confirm it does not catch up old pushes.
- [ ] Restart the service and confirm it waits for the next minute boundary.
- [ ] Send SIGTERM through systemd and confirm the process exits/restarts as expected.
- [ ] Confirm the deployed ntfy ACL permits anonymous read of `zulip_*`, denies
      anonymous write, and permits bridge-user write only.
- [ ] Confirm logs contain no message body, topic secret, auth tokens or DB password.

Once these checks pass, there are no planned MVP development items left.
