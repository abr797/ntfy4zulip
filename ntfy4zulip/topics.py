from __future__ import annotations

import base64
import hashlib
import hmac
import re

_TOPIC_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def topic_for_user(user_id: int, secret: str, prefix: str = "zulip") -> str:
    """Return a stable opaque ntfy topic for a Zulip user ID.

    The user ID is intentionally not embedded in the topic. The first 32
    base64url characters retain 192 bits of HMAC output, which is far beyond
    what is needed to make topic enumeration infeasible.
    """
    if user_id <= 0:
        raise ValueError("user_id must be positive")
    if not secret:
        raise ValueError("secret must not be empty")

    normalized_prefix = prefix.strip().strip("_-") or "zulip"
    if not _TOPIC_RE.fullmatch(normalized_prefix):
        raise ValueError("topic prefix may contain only letters, digits, '_' and '-'")

    message = f"zulip-user:{user_id}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:32]
    return f"{normalized_prefix}_{token}"
