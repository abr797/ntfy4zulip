from __future__ import annotations

from .models import NotificationCandidate


def encode_hash_component(value: str) -> str:
    """Encode one Zulip narrow URL component from the documented URL format.

    Zulip narrow fragments use ASCII alphanumerics plus "-", "_", and "~"
    literally. Every other UTF-8 byte is represented as "." followed by two
    uppercase hexadecimal digits. This includes literal "." characters.
    """
    encoded: list[str] = []
    for byte in value.encode("utf-8"):
        if (
            0x30 <= byte <= 0x39
            or 0x41 <= byte <= 0x5A
            or 0x61 <= byte <= 0x7A
            or byte in (0x2D, 0x5F, 0x7E)
        ):
            encoded.append(chr(byte))
        else:
            encoded.append(f".{byte:02X}")
    return "".join(encoded)


def _channel_slug(channel_id: int, channel_name: str) -> str:
    readable_name = channel_name.replace(" ", "-")
    return f"{int(channel_id)}-{encode_hash_component(readable_name)}"


def _dm_slug(user_ids: tuple[int, ...] | list[int]) -> str:
    ordered_ids = sorted({int(user_id) for user_id in user_ids})
    if not ordered_ids:
        raise ValueError("DM link requires at least one user ID")
    suffix = "-group" if len(ordered_ids) >= 3 else ""
    return ",".join(map(str, ordered_ids)) + suffix


def candidate_message_url(zulip_site: str, candidate: NotificationCandidate) -> str:
    base = zulip_site.rstrip("/")

    if candidate.is_channel_message:
        if candidate.stream_id is None or candidate.stream_name is None:
            raise ValueError("Channel notification is missing stream metadata")
        channel = _channel_slug(candidate.stream_id, candidate.stream_name)
        topic = encode_hash_component(candidate.topic_name)
        path = f"channel/{channel}/topic/{topic}"
    else:
        path = f"dm/{_dm_slug(candidate.dm_user_ids)}"

    return f"{base}/#narrow/{path}/near/{candidate.message_id}"
