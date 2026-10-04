from __future__ import annotations

import urllib.parse

from .models import NotificationCandidate

_HASH_REPLACEMENTS = {
    "%": ".",
    "(": ".28",
    ")": ".29",
    ".": ".2E",
}


def encode_hash_component(value: str) -> str:
    """Match Zulip Server 12.2's zerver.lib.url_encoding helper."""
    encoded = urllib.parse.quote(value, safe="")
    return "".join(_HASH_REPLACEMENTS.get(char, char) for char in encoded)


def encode_channel(channel_id: int, channel_name: str) -> str:
    channel_name = channel_name.replace(" ", "-")
    return f"{channel_id}-{encode_hash_component(channel_name)}"


def encode_user_ids(user_ids: tuple[int, ...] | list[int]) -> str:
    if not user_ids:
        raise ValueError("DM link requires at least one user ID")
    ordered = sorted(set(int(user_id) for user_id in user_ids))
    suffix = "-group" if len(ordered) >= 3 else ""
    return ",".join(str(user_id) for user_id in ordered) + suffix


def candidate_message_url(zulip_site: str, candidate: NotificationCandidate) -> str:
    base = zulip_site.rstrip("/")
    if candidate.is_channel_message:
        if candidate.stream_id is None or candidate.stream_name is None:
            raise ValueError("Channel notification is missing stream metadata")
        channel = encode_channel(candidate.stream_id, candidate.stream_name)
        topic = encode_hash_component(candidate.topic_name)
        return f"{base}/#narrow/channel/{channel}/topic/{topic}/near/{candidate.message_id}"

    slug = encode_user_ids(candidate.dm_user_ids)
    return f"{base}/#narrow/dm/{slug}/near/{candidate.message_id}"
