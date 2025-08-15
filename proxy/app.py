import os, json, logging, httpx
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

logging.basicConfig(level=logging.INFO)

AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT")  # np. https://abc123.ondigitalocean.app
AGENT_KEY = os.getenv("AGENT_ACCESS_KEY")     # Endpoint Access Key

app = FastAPI(title="DO Agent Proxy + UI (SSE-ready)", version="1.3.1")

@app.get("/")
def root():
    return {"status": "ok", "ui": "/agent/ui", "chat": "/agent/api/chat", "stream": "/agent/api/stream"}

# ---------- WERSJA BEZ PREFIKSU (działa gdy w DO: Route Path=/agent, Rewrite Path=/) ----------
@app.get("/ui")
def ui_plain():
    return FileResponse("ui.html")

@app.post("/api/chat")
async def chat_plain(req: Request):
    if not AGENT_ENDPOINT or not AGENT_KEY:
        return JSONResponse({"error": "Brak konfiguracji AGENT_ENDPOINT lub AGENT_ACCESS_KEY"}, status_code=500)

    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "Nieprawidłowe JSON"}, status_code=400)

    q = (body.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "Brak pytania"}, status_code=400)

    url = f"{AGENT_ENDPOINT.rstrip('/')}/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {AGENT_KEY}", "Content-Type": "application/json"}
    payload = {"messages": [{"role": "user", "content": q}], "stream": False}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        try:
            err_json = e.response.json()
        except Exception:
            err_json = {"error": e.response.text}
        return JSONResponse({"error": "Błąd z endpointu agenta", "details": err_json}, status_code=e.response.status_code)
    except Exception as e:
        return JSONResponse({"error": f"Błąd sieci/serwera: {e}"}, status_code=502)

    try:
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        return JSONResponse({"error": "Nieoczekiwany format odpowiedzi", "raw": data}, status_code=500)

    return {"answer": answer}

@app.get("/api/stream")
async def proxy_stream(q: str):
    if not AGENT_ENDPOINT or not AGENT_KEY:
        return JSONResponse({"error": "Brak konfiguracji AGENT_ENDPOINT lub AGENT_ACCESS_KEY"}, status_code=500)

    url = f"{AGENT_ENDPOINT.rstrip('/')}/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {AGENT_KEY}", "Content-Type": "application/json"}
    payload = {"messages": [{"role": "user", "content": q}], "stream": True}

    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data = line[len("data:"):].strip()
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                j = json.loads(data)
                                chunk = (j["choices"][0].get("delta") or {}).get("content")
                                if not chunk:
                                    chunk = (j["choices"][0].get("message") or {}).get("content")
                                if chunk:
                                    yield f"data: {chunk}\n\n"
                            except Exception:
                                yield f"data: {data}\n\n"
        except httpx.HTTPStatusError as e:
            yield f"data: [BŁĄD HTTP {e.response.status_code}]\n\n"
        except Exception as e:
            yield f"data: [BŁĄD {e}]\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

# ---------- WERSJA Z PREFIKSEM /agent (działa nawet gdy w DO zostanie włączone Preserve Prefix) ----------
agent = APIRouter(prefix="/agent")

@agent.get("/ui")
def ui_prefixed():
    return FileResponse("ui.html")

@agent.post("/api/chat")
async def chat_prefixed(req: Request):
    return await chat_plain(req)

@agent.get("/api/stream")
async def stream_prefixed(q: str):
    return await proxy_stream(q)

app.include_router(agent)

# (opcjonalnie, lokalne uruchamianie)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
