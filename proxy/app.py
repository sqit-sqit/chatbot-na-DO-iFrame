import json
from fastapi.responses import StreamingResponse

@app.get("/api/stream")
async def proxy_stream(q: str):
    if not AGENT_ENDPOINT or not AGENT_KEY:
        return JSONResponse({"error": "Brak konfiguracji AGENT_ENDPOINT lub AGENT_ACCESS_KEY"}, status_code=500)

    url = f"{AGENT_ENDPOINT.rstrip('/')}/api/v1/chat/completions"
    payload = {"messages": [{"role": "user", "content": q}], "stream": True}
    headers = {"Authorization": f"Bearer {AGENT_KEY}", "Content-Type": "application/json"}

    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        # Oczekujemy linii w formacie SSE: "data: {...}" + finalne "data: [DONE]"
                        if line.startswith("data:"):
                            data = line[len("data:"):].strip()
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                j = json.loads(data)
                                # Prefer delta.content (OpenAI-style), fallback na message.content
                                chunk = (j["choices"][0].get("delta") or {}).get("content")
                                if not chunk:
                                    chunk = (j["choices"][0].get("message") or {}).get("content")
                                if chunk:
                                    yield f"data: {chunk}\n\n"
                            except Exception:
                                # Jeśli nie-JSON, wyślij surowe
                                yield f"data: {data}\n\n"
        except httpx.HTTPStatusError as e:
            yield f"data: [BŁĄD HTTP {e.response.status_code}]\n\n"
        except Exception as e:
            yield f"data: [BŁĄD {e}]\n\n"
        finally:
            # bezpieczne domknięcie strumienia
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
