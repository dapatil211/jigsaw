import { mockApiClient } from "./mockClient";
import type {
  ApiClient,
  BoardCaptureInput,
  BoardCapturePayload,
  BoardSession,
  BoundingBox,
  GapQueryRequest,
  MatchCandidate,
  PieceScanPrompt,
  PieceScanRequest,
  Point,
  QueryResult,
  ReasonCode,
} from "../types";


interface BackendPoint {
  x: number;
  y: number;
}

interface BackendBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface BackendArtifactRef {
  artifact_id: string;
  filename: string;
  content_type: string;
  relative_path: string;
  width?: number | null;
  height?: number | null;
}

interface BackendBoardCaptureRecord {
  board_capture_id: string;
  created_at: string;
  version: number;
  payload: {
    kind: "board" | "pieces";
    corners: BackendPoint[];
    replace_current: boolean;
    label?: string | null;
  };
  board_image: BackendArtifactRef;
  rectified_image?: BackendArtifactRef | null;
}

interface BackendGapQueryRecord {
  query_id: string;
  created_at: string;
  board_capture_id: string;
  payload: {
    tap: BackendPoint;
    manual_correction?: {
      extra_tap?: BackendPoint | null;
      rough_polygon?: BackendPoint[];
    } | null;
  };
  gap_image?: BackendArtifactRef | null;
  candidates: Array<{
    candidate_id: string;
    label: string;
    source_board_capture_id?: string | null;
    source_board_capture_version?: number | null;
    score: number;
    confidence: QueryResult["confidence"];
    reasons: ReasonCode[];
    bbox?: BackendBoundingBox | null;
    is_cluster: boolean;
    needs_piece_scan: boolean;
  }>;
  confidence: QueryResult["confidence"];
  needs_manual_correction: boolean;
  message?: string | null;
}

interface BackendSessionState {
  session_id: string;
  created_at: string;
  updated_at: string;
  title?: string | null;
  board_captures: BackendBoardCaptureRecord[];
  queries: BackendGapQueryRecord[];
}

interface BackendSessionResponse {
  session: BackendSessionState;
}

interface BackendQueryResponse {
  session: BackendSessionState;
  query: BackendGapQueryRecord;
}

const fallbackClient = mockApiClient;


function apiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (envUrl) {
    return envUrl.replace(/\/$/, "");
  }

  const host = window.location.hostname || "localhost";
  return `http://${host}:8000`;
}


function artifactUrl(baseUrl: string, artifact?: BackendArtifactRef | null) {
  if (!artifact) {
    return undefined;
  }
  return `${baseUrl}/artifacts/${artifact.relative_path}`;
}


function mapPoint(point: BackendPoint): Point {
  return { x: point.x, y: point.y };
}


function mapBoundingBox(bbox?: BackendBoundingBox | null): BoundingBox | undefined {
  if (!bbox) {
    return undefined;
  }
  return {
    x: bbox.x,
    y: bbox.y,
    width: bbox.width,
    height: bbox.height,
  };
}


function buildPieceScanPrompts(candidates: MatchCandidate[]): PieceScanPrompt[] {
  return candidates
    .filter((candidate) => candidate.needsPieceScan)
    .slice(0, 3)
    .map((candidate) => ({
      candidateId: candidate.id,
      label: candidate.label,
      message: candidate.clustered
        ? "This candidate comes from a touching-piece cluster. Verify a likely piece close-up."
        : "Capture a close-up scan of this piece to strengthen the ranking.",
    }));
}


function mapCandidates(
  record: BackendGapQueryRecord
): MatchCandidate[] {
  return record.candidates.map((candidate) => ({
    id: candidate.candidate_id,
    label: candidate.label,
    sourceBoardCaptureId: candidate.source_board_capture_id ?? undefined,
    sourceBoardCaptureVersion: candidate.source_board_capture_version ?? undefined,
    score: candidate.score,
    confidence: candidate.confidence,
    clustered: candidate.is_cluster,
    needsPieceScan: candidate.needs_piece_scan,
    reasonCodes: candidate.reasons,
    bbox: mapBoundingBox(candidate.bbox),
  }));
}


function mapBoardCapture(
  baseUrl: string,
  record: BackendBoardCaptureRecord
): BoardCapturePayload {
  return {
    boardCaptureId: record.board_capture_id,
    version: record.version,
    kind: record.payload.kind,
    fileName: record.board_image.filename,
    previewUrl: artifactUrl(baseUrl, record.board_image) ?? "",
    rectifiedUrl: artifactUrl(baseUrl, record.rectified_image),
    boardCorners: record.payload.corners.map(mapPoint),
  };
}


function mapQuery(baseUrl: string, record: BackendGapQueryRecord): QueryResult {
  const candidates = mapCandidates(record);
  return {
    queryId: record.query_id,
    boardCaptureId: record.board_capture_id,
    gapTap: mapPoint(record.payload.tap),
    gapCloseupUrl: artifactUrl(baseUrl, record.gap_image),
    manualCorrection: record.payload.manual_correction
      ? {
          extraTap: record.payload.manual_correction.extra_tap
            ? mapPoint(record.payload.manual_correction.extra_tap)
            : null,
          polygon: (record.payload.manual_correction.rough_polygon ?? []).map(mapPoint),
        }
      : null,
    confidence: record.confidence,
    needsManualCorrection: record.needs_manual_correction,
    summary: record.message ?? "No summary returned by the backend.",
    candidates,
    pieceScanPrompts: buildPieceScanPrompts(candidates),
  };
}


function mapSession(baseUrl: string, session: BackendSessionState): BoardSession {
  const boardCaptures = session.board_captures.map((record) =>
    mapBoardCapture(baseUrl, record)
  );
  const queries = session.queries.map((record) => mapQuery(baseUrl, record));
  const latestBoardCapture =
    boardCaptures.length > 0 ? boardCaptures[boardCaptures.length - 1] : undefined;
  const latestQuery = queries.length > 0 ? queries[queries.length - 1] : undefined;

  return {
    id: session.session_id,
    label: session.title || session.session_id,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    boardRevisionCount: boardCaptures.length,
    queryCount: queries.length,
    boardCapture: latestBoardCapture,
    boardCaptures,
    lastQuery: latestQuery,
  };
}


async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}


export class HttpApiClient implements ApiClient {
  constructor(private readonly baseUrl = apiBaseUrl()) {}

  async listSessions(): Promise<BoardSession[]> {
    const response = await fetchJson<{ sessions: Array<{ session_id: string }> }>(
      `${this.baseUrl}/sessions`
    );
    const sessions = await Promise.all(
      response.sessions.map(async (summary) => {
        const detail = await fetchJson<BackendSessionResponse>(
          `${this.baseUrl}/sessions/${summary.session_id}`
        );
        return mapSession(this.baseUrl, detail.session);
      })
    );
    sessions.sort((left, right) =>
      (right.updatedAt ?? "").localeCompare(left.updatedAt ?? "")
    );
    return sessions;
  }

  async getSession(sessionId: string): Promise<BoardSession | undefined> {
    try {
      const detail = await fetchJson<BackendSessionResponse>(
        `${this.baseUrl}/sessions/${sessionId}`
      );
      return mapSession(this.baseUrl, detail.session);
    } catch {
      return undefined;
    }
  }

  async createSession(title?: string): Promise<BoardSession> {
    const response = await fetchJson<BackendSessionResponse>(`${this.baseUrl}/sessions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(title ? { title } : {}),
    });
    return mapSession(this.baseUrl, response.session);
  }

  async saveBoardCapture(
    sessionId: string,
    payload: BoardCaptureInput
  ): Promise<BoardSession> {
    const formData = new FormData();
    formData.append(
      "payload",
      JSON.stringify({
        corners: payload.boardCorners,
        kind: payload.kind,
        replace_current: payload.replaceCurrent ?? true,
        label: payload.label ?? null,
      })
    );
    formData.append("board_image", payload.file, payload.fileName);

    const response = await fetchJson<BackendSessionResponse & { board_capture: BackendBoardCaptureRecord }>(
      `${this.baseUrl}/sessions/${sessionId}/board-capture`,
      {
        method: "POST",
        body: formData,
      }
    );
    return mapSession(this.baseUrl, response.session);
  }

  async submitGapQuery(
    sessionId: string,
    payload: GapQueryRequest
  ): Promise<QueryResult> {
    const formData = new FormData();
    formData.append(
      "payload",
      JSON.stringify({
        board_capture_id: payload.boardCaptureId ?? null,
        candidate_capture_ids: payload.candidateCaptureIds ?? [],
        tap: payload.gapTap,
        gap_closeup_expected: Boolean(payload.gapImage),
        manual_correction: payload.manualCorrection
          ? {
              extra_tap: payload.manualCorrection.extraTap ?? null,
              rough_polygon: payload.manualCorrection.polygon,
            }
          : null,
      })
    );
    if (payload.gapImage) {
      formData.append("gap_image", payload.gapImage, payload.gapImage.name);
    }

    const response = await fetchJson<BackendQueryResponse>(
      `${this.baseUrl}/sessions/${sessionId}/gap-query`,
      {
        method: "POST",
        body: formData,
      }
    );
    return mapQuery(this.baseUrl, response.query);
  }

  async submitPieceScan(
    sessionId: string,
    payload: PieceScanRequest
  ): Promise<QueryResult> {
    const formData = new FormData();
    formData.append(
      "payload",
      JSON.stringify({
        query_id: payload.queryId,
        candidate_id: payload.candidateId,
      })
    );
    formData.append("piece_image", payload.file, payload.file.name);

    const response = await fetchJson<BackendQueryResponse & { query: BackendGapQueryRecord }>(
      `${this.baseUrl}/sessions/${sessionId}/piece-scan`,
      {
        method: "POST",
        body: formData,
      }
    );
    return mapQuery(this.baseUrl, response.query);
  }
}


function isConnectivityError(error: unknown) {
  return error instanceof TypeError || error instanceof Error;
}


export class FallbackApiClient implements ApiClient {
  constructor(
    private readonly primary: ApiClient,
    private readonly fallback: ApiClient
  ) {}

  private async withFallback<T>(operation: (client: ApiClient) => Promise<T>) {
    try {
      return await operation(this.primary);
    } catch (error) {
      if (!isConnectivityError(error)) {
        throw error;
      }
      console.warn("Falling back to mock API client:", error);
      return operation(this.fallback);
    }
  }

  async listSessions() {
    return this.withFallback((client) => client.listSessions());
  }

  async getSession(sessionId: string) {
    return this.withFallback((client) => client.getSession(sessionId));
  }

  async createSession(title?: string) {
    return this.withFallback((client) => client.createSession(title));
  }

  async saveBoardCapture(sessionId: string, payload: BoardCaptureInput) {
    return this.withFallback((client) => client.saveBoardCapture(sessionId, payload));
  }

  async submitGapQuery(sessionId: string, payload: GapQueryRequest) {
    return this.withFallback((client) => client.submitGapQuery(sessionId, payload));
  }

  async submitPieceScan(sessionId: string, payload: PieceScanRequest) {
    return this.withFallback((client) => client.submitPieceScan(sessionId, payload));
  }
}


export function createApiClient() {
  return new FallbackApiClient(new HttpApiClient(), fallbackClient);
}
