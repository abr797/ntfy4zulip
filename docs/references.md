# References and prior art

These projects and upstream sources informed the design. They are references, not
drop-in implementations of ntfy4zulip.

## Prior art

- karatch/zulip_ntfy
  https://github.com/karatch/zulip_ntfy

  Original ntfy bridge prototype. Useful for ntfy transport and Zulip event-listener
  ideas, but it sends immediately, targets predictable topics and does not implement
  all-user unread semantics or DMs.

- cyphase/zulip-to-gotify
  https://github.com/cyphase/zulip-to-gotify

  Small external Zulip-to-Gotify bridge. Useful as an example of an external
  self-hosted push transport and per-user Zulip event handling.

- patricklewis/zulip-push
  https://github.com/patricklewis/zulip-push

  Historical push experiment; useful only as background.

## Zulip Server 12.2 source of truth

- Message/UserMessage model and flags:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/messages.py

- Recipient/DirectMessageGroup model:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/recipients.py

- Stream/Subscription model:
  https://github.com/zulip/zulip/blob/12.2/zerver/models/streams.py

- URL encoding:
  https://github.com/zulip/zulip/blob/12.2/zerver/lib/url_encoding.py

- Sending messages / soft deactivation:
  https://github.com/zulip/zulip/blob/12.2/docs/subsystems/sending-messages.md

## Alternative upstream approaches

- UnifiedPush request:
  https://github.com/zulip/zulip-mobile/issues/5712

- PWA/Web Push request:
  https://github.com/zulip/zulip/issues/34240

Those approaches require changes in Zulip clients and/or server and therefore do not
meet ntfy4zulip's no-Zulip-patches constraint.

## ntfy

- Publishing:
  https://docs.ntfy.sh/publish/

- Access control:
  https://docs.ntfy.sh/config/#access-control

- Topic-name security:
  https://docs.ntfy.sh/faq/#if-topic-names-are-public-could-i-not-just-brute-force-them
