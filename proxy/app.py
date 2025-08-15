import os, httpx, logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse

logging.basicConfig(level=logging.INFO)

AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT")  # np. https://abc123.ondigitalocean.app
AGENT_KEY = os.getenv("AGENT_ACCESS_KEY")     # z Endpoint Access Keys

app = FastAPI(title="DO Agent Proxy + UI", version="1.1.0")

@app.get("/")
def root():
    return {"status": "ok", "ui": "/agent/ui", "chat": "/agent/api/chat"}

# UI do osadzania w iframe (routowane jako /agent/ui z test-site)
@app.get("/ui")
def ui():
    return FileResponse("ui.html")

# Endpoint czatu – wywołuj przez /agent/api/chat (po routingu w App Platform)
@app.post("/api/chat")
async def proxy_chat(req: Request):
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
    payload = {"messages": [{"role": "user", "content": q}], "stream": False}
    headers = {"Authorization": f"Bearer {AGENT_KEY}", "Content-Type": "application/json"}

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
