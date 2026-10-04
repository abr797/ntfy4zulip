# References and prior art

This project was designed with reference to public documentation, upstream data models,
and several existing notification-bridge projects. The current implementation is
independently written; source code from the unlicensed prior-art repositories listed
below is not included in ntfy4zulip.

## Architectural prior art

- karatch/zulip_ntfy
  https://github.com/karatch/zulip_ntfy

  Consulted as architectural prior art for an external Zulip-to-ntfy bridge. Its source
  code is not incorporated into the current implementation.

- cyphase/zulip-to-gotify
  https://github.com/cyphase/zulip-to-gotify

  Consulted as architectural prior art for forwarding Zulip events to a self-hosted
  push service. Its source code is not incorporated into the current implementation.

- patricklewis/zulip-push
  https://github.com/patricklewis/zulip-push

  Historical background for self-hosted Zulip push notifications.

## Zulip Server 12.2 compatibility references

The database integration is based on the public Zulip 12.2 data model and documentation:

- Message/UserMessage model and flags:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/messages.py

- Recipient/DirectMessageGroup model:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/recipients.py

- Stream/Subscription model:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/streams.py

- Zulip URL format:
  https://zulip.com/api/zulip-urls

- Sending messages / soft deactivation:
  https://github.com/zulip/zulip/blob/12.2/docs/subsystems/sending-messages.md

The URL encoder in ntfy4zulip is an independent implementation of the documented
narrow-URL format rather than a copy of Zulip's Python URL-encoding implementation.

## Alternative upstream approaches

- UnifiedPush request:
  https://github.com/zulip/zulip-mobile/issues/5712

- PWA/Web Push request:
  https://github.com/zulip/zulip/issues/34240

Those approaches require changes in Zulip clients and/or server and therefore do not
meet ntfy4zulip's no-Zulip-patches constraint.

## ntfy

The ntfy integration is implemented against the public ntfy documentation:

- Publishing:
  https://docs.ntfy.sh/publish/

- Access control:
  https://docs.ntfy.sh/config/#access-control

- Topic-name security:
  https://docs.ntfy.sh/faq/#if-topic-names-are-public-could-i-not-just-brute-force-them
