from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CaptureKind = Literal["board", "pieces"]

ConfidenceBucket = Literal[
    "high_confidence",
    "medium_confidence",
    "needs_piece_scan",
    "failed_extraction",
]

CandidateReasonCode = Literal[
    "shape_match",
    "cluster_uncertain",
    "low_segmentation_confidence",
    "requires_piece_scan",
    "manual_correction_used",
    "piece_scan_verified",
    "no_gap_closeup",
]


class Point(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class BoundingBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)


class ManualCorrectionInput(BaseModel):
    extra_tap: Point | None = None
    rough_polygon: list[Point] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    artifact_id: str
    filename: str
    content_type: str
    relative_path: str
    width: int | None = None
    height: int | None = None


class BoardCapturePayload(BaseModel):
    kind: CaptureKind = "board"
    corners: list[Point] = Field(default_factory=list)
    replace_current: bool = True
    label: str | None = None

    @model_validator(mode="after")
    def validate_corners(self) -> "BoardCapturePayload":
        if self.kind == "board" and len(self.corners) != 4:
            raise ValueError("Exactly 4 board corners are required.")
        if self.kind == "pieces" and len(self.corners) not in (0, 4):
            raise ValueError("Piece overview captures either omit corners or provide 4 reference corners.")
        return self


class GapQueryPayload(BaseModel):
    board_capture_id: str | None = None
    candidate_capture_ids: list[str] = Field(default_factory=list)
    tap: Point
    gap_closeup_expected: bool = False
    manual_correction: ManualCorrectionInput | None = None


class PieceScanPayload(BaseModel):
    query_id: str
    candidate_id: str | None = None
    note: str | None = None


class PieceProposal(BaseModel):
    candidate_id: str
    label: str
    source_board_capture_id: str | None = None
    source_board_capture_version: int | None = None
    bbox: BoundingBox
    area_ratio: float
    confidence: float = Field(ge=0.0, le=1.0)
    is_cluster: bool = False
    needs_closeup: bool = False
    descriptor: list[float] = Field(default_factory=list)


class MatchCandidate(BaseModel):
    candidate_id: str
    label: str
    source_board_capture_id: str | None = None
    source_board_capture_version: int | None = None
    score: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceBucket
    reasons: list[CandidateReasonCode] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    is_cluster: bool = False
    needs_piece_scan: bool = False


class QueryTarget(BaseModel):
    source_artifact_id: str | None = None
    bbox: BoundingBox
    descriptor: list[float] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    used_manual_correction: bool = False


class BoardCaptureRecord(BaseModel):
    board_capture_id: str
    created_at: datetime
    version: int
    payload: BoardCapturePayload
    board_image: ArtifactRef
    rectified_image: ArtifactRef | None = None
    piece_proposals: list[PieceProposal] = Field(default_factory=list)


class GapQueryRecord(BaseModel):
    query_id: str
    created_at: datetime
    board_capture_id: str
    payload: GapQueryPayload
    gap_image: ArtifactRef | None = None
    target: QueryTarget | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)
    confidence: ConfidenceBucket
    needs_manual_correction: bool = False
    message: str | None = None


class PieceScanRecord(BaseModel):
    piece_scan_id: str
    created_at: datetime
    query_id: str
    payload: PieceScanPayload
    piece_image: ArtifactRef
    updated_candidates: list[MatchCandidate] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    board_captures: list[BoardCaptureRecord] = Field(default_factory=list)
    queries: list[GapQueryRecord] = Field(default_factory=list)
    piece_scans: list[PieceScanRecord] = Field(default_factory=list)


class SessionSummary(BaseModel):
    session_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    board_capture_count: int
    query_count: int


class CreateSessionRequest(BaseModel):
    title: str | None = None


class CreateSessionResponse(BaseModel):
    session: SessionState


class ListSessionsResponse(BaseModel):
    sessions: list[SessionSummary]


class SessionDetailResponse(BaseModel):
    session: SessionState


class BoardCaptureResponse(BaseModel):
    session: SessionState
    board_capture: BoardCaptureRecord


class GapQueryResponse(BaseModel):
    session: SessionState
    query: GapQueryRecord


class PieceScanResponse(BaseModel):
    session: SessionState
    piece_scan: PieceScanRecord
    query: GapQueryRecord | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
