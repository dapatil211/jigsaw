export interface Point {
  x: number;
  y: number;
}

export type CaptureKind = "board" | "pieces";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type ConfidenceBucket =
  | "high_confidence"
  | "medium_confidence"
  | "needs_piece_scan"
  | "failed_extraction";

export type ReasonCode =
  | "shape_match"
  | "cluster_uncertain"
  | "low_segmentation_confidence"
  | "requires_piece_scan"
  | "manual_correction_used"
  | "piece_scan_verified"
  | "no_gap_closeup";

export interface ManualCorrection {
  extraTap?: Point | null;
  polygon: Point[];
}

export interface BoardCapturePayload {
  boardCaptureId: string;
  version: number;
  kind: CaptureKind;
  fileName: string;
  previewUrl: string;
  rectifiedUrl?: string;
  boardCorners: Point[];
}

export interface BoardCaptureInput {
  file: File;
  fileName: string;
  previewUrl: string;
  kind: CaptureKind;
  boardCorners: Point[];
  replaceCurrent?: boolean;
  label?: string;
}

export interface GapQueryRequest {
  boardCaptureId?: string;
  candidateCaptureIds?: string[];
  gapTap: Point;
  gapImage?: File | null;
  gapCloseupUrl?: string;
  manualCorrection?: ManualCorrection | null;
}

export interface MatchCandidate {
  id: string;
  label: string;
  sourceBoardCaptureId?: string;
  sourceBoardCaptureVersion?: number;
  score: number;
  confidence: ConfidenceBucket;
  clustered: boolean;
  needsPieceScan: boolean;
  reasonCodes: ReasonCode[];
  bbox?: BoundingBox;
}

export interface PieceScanPrompt {
  candidateId: string;
  label: string;
  message: string;
}

export interface QueryResult {
  queryId: string;
  boardCaptureId: string;
  gapTap: Point;
  gapCloseupUrl?: string;
  manualCorrection: ManualCorrection | null;
  confidence: ConfidenceBucket;
  needsManualCorrection: boolean;
  summary: string;
  candidates: MatchCandidate[];
  pieceScanPrompts: PieceScanPrompt[];
}

export interface BoardSession {
  id: string;
  label: string;
  createdAt?: string;
  updatedAt?: string;
  boardRevisionCount: number;
  queryCount: number;
  boardCapture?: BoardCapturePayload;
  boardCaptures: BoardCapturePayload[];
  lastQuery?: QueryResult;
}

export interface PieceScanRequest {
  queryId: string;
  candidateId: string;
  file: File;
}

export interface ApiClient {
  listSessions(): Promise<BoardSession[]>;
  getSession(sessionId: string): Promise<BoardSession | undefined>;
  createSession(title?: string): Promise<BoardSession>;
  saveBoardCapture(
    sessionId: string,
    payload: BoardCaptureInput
  ): Promise<BoardSession>;
  submitGapQuery(sessionId: string, payload: GapQueryRequest): Promise<QueryResult>;
  submitPieceScan(sessionId: string, payload: PieceScanRequest): Promise<QueryResult>;
}
