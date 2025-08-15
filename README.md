# DO AI Sandbox – iframe (Private)

Ten wariant osadza UI agenta przez **iframe**, ale nadal zachowuje **Private** endpoint agenta.
Schemat:
- `test-site/` serwuje stronę z `<iframe src="/agent/ui">`.
- `proxy/` serwuje **UI** (`/ui`) oraz **API** (`/api/chat`) i łączy się z prywatnym Agentem DO przez **Agent Access Key**.
- W **Networking (HTTP Request Routes)** konfigurujemy **prefiks `/agent`** dla komponentu `proxy`:
  - Route Path: `/agent`
  - Rewrite Path: `/` (zalecane)
    - `/agent/ui` → kontener dostaje `/ui`
    - `/agent/api/chat` → kontener dostaje `/api/chat`

## Struktura
- `test-site/index.html` – główna strona z iframe.
- `proxy/ui.html` – UI chatu ładowane w iframe.
- `proxy/app.py` – FastAPI serwujące `/ui` i `/api/chat` + root `/` (health check).
- `proxy/requirements.txt`

## Deploy – skrót
1) App Platform → Create App → dodaj komponenty:
   - **Static Site**: folder `test-site/`
   - **Web Service**: folder `proxy/`, run:
     ```
     uvicorn app:app --host 0.0.0.0 --port 8080
     ```

2) Zmienne środowiskowe (komponent **proxy**):
   - `AGENT_ENDPOINT` = URL endpointu agenta (np. `https://abc123.ondigitalocean.app`)
   - `AGENT_ACCESS_KEY` = Endpoint Access Key

3) Routing (HTTP Request Routes):
   - W komponencie **proxy**:
     - Route Path: `/agent`
     - Rewrite Path: `/`
   - W komponencie **test-site**:
     - Route Path: `/`
     - Rewrite Path: (puste)

4) Wejdź na stronę testową – iframe załaduje `/agent/ui`, a tamten UI będzie trafiał do prywatnego agenta przez Twoje proxy.

## Debug
- Health check: `GET /` na komponencie `proxy` zwraca 200.
- Jeśli dostaniesz CORS, to znaczy, że korzystasz z innego origin — w tym układzie wszystko idzie przez **ten sam origin**, więc CORS nie powinien się pojawić.
