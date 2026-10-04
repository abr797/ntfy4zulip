from __future__ import annotations

import os

from aiohttp import web


async def publish(request: web.Request) -> web.Response:
    expected_token = request.app["expected_token"]
    if expected_token is not None:
        supplied = request.headers.get("Authorization")
        if supplied != f"Bearer {expected_token}":
            return web.json_response({"error": "unauthorized"}, status=401)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if not isinstance(payload, dict):
        return web.json_response({"error": "JSON object required"}, status=400)

    topic = payload.get("topic")
    message = payload.get("message")
    if not isinstance(topic, str) or not topic:
        return web.json_response({"error": "topic is required"}, status=400)
    if not isinstance(message, str):
        return web.json_response({"error": "message is required"}, status=400)

    print(
        "mock ntfy received "
        f"topic={topic!r} title={payload.get('title')!r} "
        f"priority={payload.get('priority')!r} click={payload.get('click')!r}"
    )
    print(message)

    response = {
        "id": "mock-1",
        "event": "message",
        "topic": topic,
        "message": message,
    }
    if isinstance(payload.get("title"), str):
        response["title"] = payload["title"]
    return web.json_response(response)


def create_app(expected_token: str | None = None) -> web.Application:
    app = web.Application()
    app["expected_token"] = expected_token
    app.router.add_post("/", publish)
    return app


if __name__ == "__main__":
    token = os.getenv("MOCK_NTFY_AUTH_TOKEN") or None
    web.run_app(create_app(token), host="127.0.0.1", port=8081)
