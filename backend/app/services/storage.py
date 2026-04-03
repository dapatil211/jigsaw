from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.models.schemas import ArtifactRef, SessionState, SessionSummary


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def session_file(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def artifact_dir(self, session_id: str, category: str) -> Path:
        path = self.session_dir(session_id) / "artifacts" / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_session(self, title: str | None = None) -> SessionState:
        session_id = f"session-{uuid4().hex[:12]}"
        now = utcnow()
        session = SessionState(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            title=title,
        )
        self.save_session(session)
        return session

    def save_session(self, session: SessionState) -> SessionState:
        session_path = self.session_file(session.session_id)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session.updated_at = utcnow()
        session_path.write_text(
            json.dumps(session.model_dump(mode="json"), indent=2, sort_keys=True)
        )
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        session_path = self.session_file(session_id)
        if not session_path.exists():
            return None
        return SessionState.model_validate_json(session_path.read_text())

    def list_sessions(self) -> list[SessionSummary]:
        sessions: list[SessionSummary] = []
        for session_path in sorted(self.root.glob("session-*/session.json")):
            session = SessionState.model_validate_json(session_path.read_text())
            sessions.append(
                SessionSummary(
                    session_id=session.session_id,
                    title=session.title,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    board_capture_count=len(session.board_captures),
                    query_count=len(session.queries),
                )
            )
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return sessions

    def mutate_session(
        self, session_id: str, mutator: Callable[[SessionState], object]
    ) -> tuple[SessionState, object]:
        session = self.get_session(session_id)
        if session is None:
            raise FileNotFoundError(session_id)
        result = mutator(session)
        self.save_session(session)
        return session, result

    def next_board_version(self, session: SessionState) -> int:
        if not session.board_captures:
            return 1
        return max(item.version for item in session.board_captures) + 1

    def store_artifact(
        self,
        session_id: str,
        category: str,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> ArtifactRef:
        safe_name = Path(filename).name or f"{category}.bin"
        artifact_id = f"{category}-{uuid4().hex[:12]}"
        path = self.artifact_dir(session_id, category) / f"{artifact_id}-{safe_name}"
        path.write_bytes(content)
        relative_path = path.relative_to(self.root.parent)
        return ArtifactRef(
            artifact_id=artifact_id,
            filename=safe_name,
            content_type=content_type,
            relative_path=str(relative_path),
            width=width,
            height=height,
        )
