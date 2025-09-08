# LoquiLex API

FastAPI-based glue to orchestrate ASR+MT sessions and stream events.

Run

- Ensure Python env has fastapi, uvicorn.
- Start: `python -m uvicorn loquilex.api.server:app --port 8000 --host 0.0.0.0`

Endpoints

- GET /models/asr
- GET /models/mt
- GET /languages/mt/{id}
- POST /models/download
- POST /sessions
- DELETE /sessions/{sid}
- WS /events/{sid}