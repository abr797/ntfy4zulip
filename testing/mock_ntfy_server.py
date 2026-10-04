from aiohttp import web

EXPECTED_AUTH_TOKEN = "tk_abcdef123456789"


def auth_ok(request: web.Request) -> bool:
    return request.headers.get("Authorization", "") == f"Bearer {EXPECTED_AUTH_TOKEN}"


async def handle_legacy_post(request: web.Request) -> web.Response:
    topic_name = request.match_info["topic"]
    body_text = (await request.read()).decode("utf-8")
    payload = {
        "topic": topic_name,
        "title": request.headers.get("Title", "[Без заголовка]"),
        "message": body_text,
        "click": request.headers.get("X-Click", ""),
        "tags": request.headers.get("X-Tags", ""),
        "priority": request.headers.get("X-Priority", "3"),
        "markdown": request.headers.get("X-Markdown", "no"),
    }
    return show_and_respond(payload, auth_ok(request))


async def handle_json_post(request: web.Request) -> web.Response:
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("topic"):
        return web.json_response({"error": "topic is required"}, status=400)
    return show_and_respond(payload, auth_ok(request))


def show_and_respond(payload: dict, authorized: bool) -> web.Response:
    print("\n" + "=" * 60)
    print("[ntfy Server] ПЕРЕХВАЧЕН ИСХОДЯЩИЙ ПУШ!")
    print(f"Целевой топик: {payload.get('topic')}")
    print(f"Статус авторизации: {'Успешно (Bearer)' if authorized else 'Неавторизованный'}")
    print("-" * 40)
    print(f"Заголовок: {payload.get('title', '[Без заголовка]')}")
    print(f"Priority: {payload.get('priority', 3)} | Tags: {payload.get('tags', [])}")
    print(f"Markdown: {payload.get('markdown', False)}")
    print(f"Click: {payload.get('click', '')}")
    print("-" * 40)
    print(f"Тело сообщения:\n{payload.get('message', '')}")
    print("=" * 60 + "\n")

    return web.json_response(
        {
            "id": "m_test12345abcde",
            "time": 1700000000,
            "expires": 1700043200,
            "event": "message",
            "topic": payload.get("topic"),
            "title": payload.get("title"),
            "message": payload.get("message", ""),
        },
        status=200,
    )


app = web.Application()
app.router.add_post("/", handle_json_post)
app.router.add_post("/{topic}", handle_legacy_post)

if __name__ == "__main__":
    print("Локальный Mock-сервер ntfy запущен на http://127.0.0.1:8081")
    web.run_app(app, port=8081)
