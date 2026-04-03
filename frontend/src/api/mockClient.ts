import type {
  ApiClient,
  BoardCaptureInput,
  BoardCapturePayload,
  BoardSession,
  GapQueryRequest,
  ManualCorrection,
  MatchCandidate,
  PieceScanPrompt,
  PieceScanRequest,
  QueryResult,
} from "../types";


const storageKey = "jigsaw-assistant-mock-sessions";


function loadSessions(): BoardSession[] {
  const raw = localStorage.getItem(storageKey);
  if (!raw) {
    return [buildSeedSession()];
  }

  try {
    return JSON.parse(raw) as BoardSession[];
  } catch {
    return [buildSeedSession()];
  }
}


function persistSessions(sessions: BoardSession[]) {
  localStorage.setItem(storageKey, JSON.stringify(sessions));
}


function buildSeedSession(): BoardSession {
  const boardCapture: BoardCapturePayload = {
    boardCaptureId: "board-seed-001",
    version: 1,
    kind: "board",
    fileName: "seed-board.jpg",
    previewUrl:
      "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=900&q=80",
    boardCorners: [
      { x: 0.14, y: 0.18 },
      { x: 0.87, y: 0.19 },
      { x: 0.85, y: 0.83 },
      { x: 0.16, y: 0.82 },
    ],
  };
  const pieceCaptureTwo: BoardCapturePayload = {
    boardCaptureId: "board-seed-002",
    version: 2,
    kind: "pieces",
    fileName: "pieces-overview-a.jpg",
    previewUrl:
      "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80",
    boardCorners: [],
  };
  const pieceCaptureThree: BoardCapturePayload = {
    boardCaptureId: "board-seed-003",
    version: 3,
    kind: "pieces",
    fileName: "pieces-overview-b.jpg",
    previewUrl:
      "https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=900&q=80",
    boardCorners: [],
  };

  return {
    id: "session-seed-001",
    label: "Living room board",
    boardRevisionCount: 3,
    queryCount: 1,
    boardCapture,
    boardCaptures: [boardCapture, pieceCaptureTwo, pieceCaptureThree],
    lastQuery: {
      queryId: "query-seed-001",
      boardCaptureId: boardCapture.boardCaptureId,
      gapTap: { x: 0.54, y: 0.46 },
      gapCloseupUrl:
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80",
      manualCorrection: null,
      confidence: "needs_piece_scan",
      needsManualCorrection: false,
      summary:
        "Top candidates are close. Two come from touching-piece clusters, so the assistant is asking for verification scans.",
      candidates: buildCandidates("needs_piece_scan"),
      pieceScanPrompts: buildPieceScanPrompts("needs_piece_scan"),
    },
  };
}


function createSessionRecord(index: number): BoardSession {
  const now = new Date().toISOString();
  return {
    id: `session-${Date.now()}-${index}`,
    label: `Tabletop run ${index + 1}`,
    createdAt: now,
    updatedAt: now,
    boardRevisionCount: 0,
    queryCount: 0,
    boardCaptures: [],
  };
}


function buildCandidates(mode: QueryResult["confidence"]): MatchCandidate[] {
  return [
    {
      id: "piece-18",
      label: "Pieces v2 region 18",
      sourceBoardCaptureId: "board-seed-002",
      sourceBoardCaptureVersion: 2,
      score: mode === "high_confidence" ? 0.92 : 0.74,
      confidence: mode === "high_confidence" ? "high_confidence" : "medium_confidence",
      clustered: false,
      needsPieceScan: mode !== "high_confidence",
      reasonCodes: ["shape_match"],
    },
    {
      id: "cluster-04",
      label: "Pieces v3 region 04",
      sourceBoardCaptureId: "board-seed-003",
      sourceBoardCaptureVersion: 3,
      score: mode === "failed_extraction" ? 0.55 : 0.69,
      confidence: "needs_piece_scan",
      clustered: true,
      needsPieceScan: true,
      reasonCodes: ["cluster_uncertain", "requires_piece_scan"],
    },
    {
      id: "piece-42",
      label: "Pieces v1 region 42",
      sourceBoardCaptureId: "board-seed-001",
      sourceBoardCaptureVersion: 1,
      score: mode === "failed_extraction" ? 0.51 : 0.67,
      confidence: "medium_confidence",
      clustered: false,
      needsPieceScan: true,
      reasonCodes: ["shape_match"],
    },
  ];
}


function buildPieceScanPrompts(
  confidence: QueryResult["confidence"]
): PieceScanPrompt[] {
  if (confidence === "high_confidence") {
    return [];
  }

  return [
    {
      candidateId: "piece-18",
      label: "Scan Piece 18",
      message: "Strong coarse match. A close-up scan should confirm the fit.",
    },
    {
      candidateId: "cluster-04",
      label: "Check cluster region 04",
      message:
        "This region contains touching pieces. Scan the best visible piece to disambiguate the cluster.",
    },
  ];
}


function confidenceFromRequest(
  manualCorrection: ManualCorrection | null,
  gapCloseupUrl?: string
): QueryResult["confidence"] {
  if (manualCorrection?.polygon.length || gapCloseupUrl) {
    return "needs_piece_scan";
  }
  return "failed_extraction";
}


class MockApiClient implements ApiClient {
  private sessions = loadSessions();

  async listSessions(): Promise<BoardSession[]> {
    return this.sessions;
  }

  async getSession(sessionId: string): Promise<BoardSession | undefined> {
    return this.sessions.find((session) => session.id === sessionId);
  }

  async createSession(): Promise<BoardSession> {
    const session = createSessionRecord(this.sessions.length);
    this.sessions = [session, ...this.sessions];
    persistSessions(this.sessions);
    return session;
  }

  async saveBoardCapture(
    sessionId: string,
    payload: BoardCaptureInput
  ): Promise<BoardSession> {
    const boardCapture: BoardCapturePayload = {
      boardCaptureId: `board-${Date.now()}`,
      version:
        (this.sessions.find((session) => session.id === sessionId)?.boardRevisionCount ?? 0) + 1,
      kind: payload.kind,
      fileName: payload.fileName,
      previewUrl: payload.previewUrl,
      boardCorners: payload.boardCorners,
    };

    this.sessions = this.sessions.map((session) =>
      session.id === sessionId
        ? {
            ...session,
            boardCapture,
            boardCaptures: [...session.boardCaptures, boardCapture],
            boardRevisionCount: session.boardRevisionCount + 1,
            updatedAt: new Date().toISOString(),
          }
        : session
    );
    persistSessions(this.sessions);
    return this.sessions.find((session) => session.id === sessionId)!;
  }

  async submitGapQuery(
    sessionId: string,
    payload: GapQueryRequest
  ): Promise<QueryResult> {
    const confidence = confidenceFromRequest(
      payload.manualCorrection ?? null,
      payload.gapCloseupUrl
    );
    const session = this.sessions.find((item) => item.id === sessionId);
    const boardCaptureId =
      payload.boardCaptureId ?? session?.boardCapture?.boardCaptureId ?? "board-missing";

    const result: QueryResult = {
      queryId: `query-${Date.now()}`,
      boardCaptureId,
      gapTap: payload.gapTap,
      gapCloseupUrl: payload.gapCloseupUrl,
      manualCorrection: payload.manualCorrection ?? null,
      confidence,
      needsManualCorrection: confidence === "failed_extraction",
      summary:
        confidence === "failed_extraction"
          ? "Gap extraction is weak. Add a close-up or a rough polygon, then resubmit."
          : "Coarse ranking is ready. Scan one or two top candidates to improve confidence.",
      candidates: buildCandidates(confidence),
      pieceScanPrompts: buildPieceScanPrompts(confidence),
    };

    this.sessions = this.sessions.map((item) =>
      item.id === sessionId
        ? {
            ...item,
            lastQuery: result,
            queryCount: item.queryCount + 1,
            updatedAt: new Date().toISOString(),
          }
        : item
    );
    persistSessions(this.sessions);
    return result;
  }

  async submitPieceScan(
    sessionId: string,
    payload: PieceScanRequest
  ): Promise<QueryResult> {
    const current = this.sessions.find((session) => session.id === sessionId)?.lastQuery;
    const result: QueryResult = {
      queryId: payload.queryId,
      boardCaptureId: current?.boardCaptureId ?? "board-missing",
      gapTap: current?.gapTap ?? { x: 0.5, y: 0.5 },
      gapCloseupUrl: current?.gapCloseupUrl,
      manualCorrection: current?.manualCorrection ?? null,
      confidence: "high_confidence",
      needsManualCorrection: false,
      summary: `${payload.file.name} improved the ranking. The top candidate is now strong enough to test on the board.`,
      candidates: [
        {
          id: payload.candidateId,
          label: payload.candidateId === "cluster-04" ? "Cluster region 04" : "Piece 18",
          score: 0.93,
          confidence: "high_confidence",
          clustered: false,
          needsPieceScan: false,
          reasonCodes: ["piece_scan_verified", "shape_match"],
        },
        ...buildCandidates("high_confidence").filter(
          (candidate) => candidate.id !== payload.candidateId
        ),
      ],
      pieceScanPrompts: [],
    };

    this.sessions = this.sessions.map((session) =>
      session.id === sessionId
        ? {
            ...session,
            lastQuery: result,
            updatedAt: new Date().toISOString(),
          }
        : session
    );
    persistSessions(this.sessions);
    return result;
  }
}


export const mockApiClient = new MockApiClient();
