# Backend

This package hosts the FastAPI service for:

- session lifecycle
- image ingestion
- artifact storage
- board rectification
- gap extraction
- piece ranking
- close-up verification

## Endpoints

- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `POST /sessions/{session_id}/board-capture`
- `POST /sessions/{session_id}/gap-query`
- `GET /sessions/{session_id}/queries/{query_id}`
- `POST /sessions/{session_id}/piece-scan`

The service is LAN-oriented for v1 and uses persistent file-backed sessions under `../data/sessions`.

## Local Run

```bash
uv sync --project backend
uv run --project backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Artifacts are served back to the frontend under `/artifacts/...` so persistent sessions can reopen saved board and scan images.
