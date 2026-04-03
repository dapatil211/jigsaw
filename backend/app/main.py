from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.sessions import router as sessions_router
from app.services.storage import SessionStorage


def create_app() -> FastAPI:
    app = FastAPI(title="Jigsaw Assistant API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=(
            r"https?://("
            r"localhost|127\.0\.0\.1|"
            r"[A-Za-z0-9-]+\.local|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    data_root = Path(__file__).resolve().parents[2] / "data" / "sessions"
    app.state.storage = SessionStorage(data_root)
    app.include_router(sessions_router)
    app.mount("/artifacts", StaticFiles(directory=data_root.parent), name="artifacts")
    return app


app = create_app()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
