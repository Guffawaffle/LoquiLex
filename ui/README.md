# Greenfield UI

React/Vite UI to control multiple ASR+MT sessions via the Greenfield FastAPI backend.

Quickstart

- Backend: run the API server
  - Python env should have FastAPI and uvicorn available.
- Frontend: run Vite dev server

Backend

- Module: `greenfield.api.server:app`
- Run with uvicorn on port 8000.

Frontend

- Directory: `greenfield/ui/web`
- Dev server on http://localhost:5173 (proxy to backend on 8000)