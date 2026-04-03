from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.models.schemas import (
    ArtifactRef,
    BoardCapturePayload,
    BoardCaptureRecord,
    BoardCaptureResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    GapQueryPayload,
    GapQueryRecord,
    GapQueryResponse,
    ListSessionsResponse,
    PieceScanPayload,
    PieceScanRecord,
    PieceScanResponse,
    SessionDetailResponse,
    SessionState,
)
from app.services.storage import utcnow
from app.services.vision import (
    analyze_board_capture,
    analyze_gap_query,
    analyze_piece_scan,
    read_image_dimensions,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _parse_json_payload(raw: str, model_type):
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
    try:
        return model_type.model_validate(payload)
    except Exception as exc:  # pragma: no cover - FastAPI renders validation details poorly here
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get_storage(request: Request):
    return request.app.state.storage


async def _store_upload(request: Request, session_id: str, category: str, file: UploadFile) -> ArtifactRef:
    storage = _get_storage(request)
    content = await file.read()
    width, height = read_image_dimensions(content)
    return storage.store_artifact(
        session_id,
        category,
        file.filename or f"{category}.jpg",
        content,
        file.content_type or "application/octet-stream",
        width=width,
        height=height,
    )


@router.post("", response_model=CreateSessionResponse)
def create_session(
    request: Request, payload: CreateSessionRequest | None = None
) -> CreateSessionResponse:
    storage = _get_storage(request)
    session = storage.create_session(title=payload.title if payload else None)
    return CreateSessionResponse(session=session)


@router.get("", response_model=ListSessionsResponse)
def list_sessions(request: Request) -> ListSessionsResponse:
    storage = _get_storage(request)
    return ListSessionsResponse(sessions=storage.list_sessions())


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session(request: Request, session_id: str) -> SessionDetailResponse:
    storage = _get_storage(request)
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return SessionDetailResponse(session=session)


@router.post("/{session_id}/board-capture", response_model=BoardCaptureResponse)
async def board_capture(
    request: Request,
    session_id: str,
    payload: str = Form(...),
    board_image: UploadFile = File(...),
) -> BoardCaptureResponse:
    storage = _get_storage(request)
    board_payload = _parse_json_payload(payload, BoardCapturePayload)
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    board_artifact = await _store_upload(request, session_id, "board", board_image)

    def mutate(state: SessionState) -> BoardCaptureRecord:
        version = storage.next_board_version(state)
        board_capture_id = f"board-{uuid4().hex[:12]}"
        analysis = analyze_board_capture(
            storage.root.parent / board_artifact.relative_path, board_payload
        )
        rectified_artifact = None
        if analysis.rectified_image_bytes is not None:
            rectified_artifact = storage.store_artifact(
                session_id,
                "rectified",
                f"board-v{version}.png",
                analysis.rectified_image_bytes,
                "image/png",
                width=analysis.rectified_width,
                height=analysis.rectified_height,
            )
        piece_proposals = [
            proposal.model_copy(
                update={
                    "candidate_id": f"capture-{version:02d}-{index + 1:03d}",
                    "label": (
                        f"{'Board' if board_payload.kind == 'board' else 'Pieces'} v{version} "
                        f"region {index + 1}"
                    ),
                    "source_board_capture_id": board_capture_id,
                    "source_board_capture_version": version,
                }
            )
            for index, proposal in enumerate(analysis.piece_proposals)
        ]
        record = BoardCaptureRecord(
            board_capture_id=board_capture_id,
            created_at=utcnow(),
            version=version,
            payload=board_payload,
            board_image=board_artifact,
            rectified_image=rectified_artifact,
            piece_proposals=piece_proposals,
        )
        state.board_captures.append(record)
        return record

    session, record = storage.mutate_session(session_id, mutate)
    return BoardCaptureResponse(session=session, board_capture=record)


@router.post("/{session_id}/gap-query", response_model=GapQueryResponse)
async def gap_query(
    request: Request,
    session_id: str,
    payload: str = Form(...),
    gap_image: UploadFile | None = File(default=None),
) -> GapQueryResponse:
    storage = _get_storage(request)
    query_payload = _parse_json_payload(payload, GapQueryPayload)
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    board_capture = None
    if query_payload.board_capture_id:
        for capture in session.board_captures:
            if capture.board_capture_id == query_payload.board_capture_id:
                board_capture = capture
                break
    elif session.board_captures:
        board_capture = next(
            (capture for capture in reversed(session.board_captures) if capture.payload.kind == "board"),
            None,
        )
    if board_capture is None or board_capture.payload.kind != "board":
        raise HTTPException(status_code=400, detail="No board capture available.")

    if query_payload.candidate_capture_ids:
        candidate_captures = [
            capture
            for capture in session.board_captures
            if capture.board_capture_id in query_payload.candidate_capture_ids
        ]
    else:
        candidate_captures = list(session.board_captures)
    if not candidate_captures:
        candidate_captures = [board_capture]

    gap_artifact = None
    gap_path = None
    if gap_image is not None:
        gap_artifact = await _store_upload(request, session_id, "gap", gap_image)
        gap_path = storage.root.parent / gap_artifact.relative_path

    board_path = storage.root.parent / board_capture.board_image.relative_path

    def mutate(state: SessionState) -> GapQueryRecord:
        analysis = analyze_gap_query(
            board_path,
            gap_path,
            board_capture,
            candidate_captures,
            query_payload,
        )
        record = GapQueryRecord(
            query_id=f"query-{uuid4().hex[:12]}",
            created_at=utcnow(),
            board_capture_id=board_capture.board_capture_id,
            payload=query_payload,
            gap_image=gap_artifact,
            target=analysis.target,
            candidates=analysis.candidates,
            confidence=analysis.confidence,
            needs_manual_correction=analysis.needs_manual_correction,
            message=analysis.message,
        )
        state.queries.append(record)
        return record

    session, record = storage.mutate_session(session_id, mutate)
    return GapQueryResponse(session=session, query=record)


@router.get("/{session_id}/queries/{query_id}", response_model=GapQueryResponse)
def get_query(
    request: Request, session_id: str, query_id: str
) -> GapQueryResponse:
    storage = _get_storage(request)
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    for query in session.queries:
        if query.query_id == query_id:
            return GapQueryResponse(session=session, query=query)
    raise HTTPException(status_code=404, detail="Query not found.")


@router.post("/{session_id}/piece-scan", response_model=PieceScanResponse)
async def piece_scan(
    request: Request,
    session_id: str,
    payload: str = Form(...),
    piece_image: UploadFile = File(...),
) -> PieceScanResponse:
    storage = _get_storage(request)
    scan_payload = _parse_json_payload(payload, PieceScanPayload)
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    query = next((item for item in session.queries if item.query_id == scan_payload.query_id), None)
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found.")
    artifact = await _store_upload(request, session_id, "piece-scan", piece_image)
    piece_path = storage.root.parent / artifact.relative_path

    def mutate(state: SessionState) -> tuple[PieceScanRecord, GapQueryRecord]:
        session_query = next(item for item in state.queries if item.query_id == scan_payload.query_id)
        analysis = analyze_piece_scan(piece_path, session_query, scan_payload)
        if analysis.updated_query is not None:
            session_query.candidates = analysis.updated_query.candidates
            session_query.confidence = analysis.updated_query.confidence
            session_query.message = analysis.updated_query.message
        record = PieceScanRecord(
            piece_scan_id=f"scan-{uuid4().hex[:12]}",
            created_at=utcnow(),
            query_id=scan_payload.query_id,
            payload=scan_payload,
            piece_image=artifact,
            updated_candidates=session_query.candidates,
        )
        state.piece_scans.append(record)
        return record, session_query

    session, result = storage.mutate_session(session_id, mutate)
    piece_scan_record, updated_query = result
    return PieceScanResponse(
        session=session, piece_scan=piece_scan_record, query=updated_query
    )
