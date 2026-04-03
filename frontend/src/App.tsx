import { useEffect, useMemo, useState } from "react";

import { createApiClient } from "./api/httpClient";
import { ImageTapTarget } from "./components/ImageTapTarget";
import { StatusPill } from "./components/StatusPill";
import type {
  ApiClient,
  BoardSession,
  CaptureKind,
  GapQueryRequest,
  ManualCorrection,
  MatchCandidate,
  PieceScanRequest,
  Point,
  QueryResult,
} from "./types";


function useObjectUrl(file?: File | null) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    if (!file) {
      setUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  return url;
}


function mapConfidenceState(confidence?: QueryResult["confidence"]) {
  if (confidence === "high_confidence" || confidence === "medium_confidence") {
    return "complete" as const;
  }
  if (confidence === "failed_extraction" || confidence === "needs_piece_scan") {
    return "warning" as const;
  }
  return "pending" as const;
}


function formatPercent(point: Point) {
  return `${Math.round(point.x * 100)}%, ${Math.round(point.y * 100)}%`;
}


function captureLabel(kind: CaptureKind) {
  return kind === "board" ? "Board photo" : "Loose-piece overview";
}


const GRID_COLUMNS = 4;
const GRID_ROWS = 4;


function gridCellLabel(candidate: MatchCandidate) {
  if (!candidate.bbox) {
    return null;
  }

  const centerX = candidate.bbox.x + candidate.bbox.width / 2;
  const centerY = candidate.bbox.y + candidate.bbox.height / 2;
  const columnIndex = Math.min(GRID_COLUMNS - 1, Math.max(0, Math.floor(centerX * GRID_COLUMNS)));
  const rowIndex = Math.min(GRID_ROWS - 1, Math.max(0, Math.floor(centerY * GRID_ROWS)));
  const columnLabel = String.fromCharCode(65 + columnIndex);
  return `${columnLabel}${rowIndex + 1}`;
}


function App() {
  const apiClient = useMemo<ApiClient>(() => createApiClient(), []);
  const [sessions, setSessions] = useState<BoardSession[]>([]);
  const [session, setSession] = useState<BoardSession | null>(null);
  const [sessionTitle, setSessionTitle] = useState("");
  const [captureKind, setCaptureKind] = useState<CaptureKind>("board");
  const [boardFile, setBoardFile] = useState<File | null>(null);
  const [boardCorners, setBoardCorners] = useState<Point[]>([]);
  const [gapFile, setGapFile] = useState<File | null>(null);
  const [gapTap, setGapTap] = useState<Point[]>([]);
  const [manualExtraTap, setManualExtraTap] = useState<Point[]>([]);
  const [manualPolygon, setManualPolygon] = useState<Point[]>([]);
  const [pieceFiles, setPieceFiles] = useState<File[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [selectedGapBoardCaptureId, setSelectedGapBoardCaptureId] = useState("");
  const [selectedCandidateCaptureIds, setSelectedCandidateCaptureIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("Create or load a session to begin.");

  const boardPreview = useObjectUrl(boardFile);
  const gapPreview = useObjectUrl(gapFile);
  const activeQuery = session?.lastQuery;
  const boardCaptures = session?.boardCaptures ?? [];
  const gapBoardOptions = boardCaptures.filter((capture) => capture.kind === "board");
  const selectedGapBoardCapture =
    gapBoardOptions.find((capture) => capture.boardCaptureId === selectedGapBoardCaptureId) ??
    gapBoardOptions[gapBoardOptions.length - 1];
  const activeBoardImage = boardPreview || selectedGapBoardCapture?.previewUrl || "";
  const activeGapImage = gapPreview || activeQuery?.gapCloseupUrl || activeBoardImage;

  useEffect(() => {
    void loadSessions();
  }, [apiClient]);

  useEffect(() => {
    if (!session) {
      setSelectedGapBoardCaptureId("");
      setSelectedCandidateCaptureIds([]);
      return;
    }

    setSelectedGapBoardCaptureId((current) => {
      if (current && gapBoardOptions.some((capture) => capture.boardCaptureId === current)) {
        return current;
      }
      return gapBoardOptions[gapBoardOptions.length - 1]?.boardCaptureId ?? "";
    });

    setSelectedCandidateCaptureIds((current) => {
      const valid = current.filter((captureId) =>
        boardCaptures.some((capture) => capture.boardCaptureId === captureId)
      );
      return valid.length ? valid : boardCaptures.map((capture) => capture.boardCaptureId);
    });
  }, [session, boardCaptures.length, gapBoardOptions.length]);

  async function loadSessions(selectSessionId?: string) {
    setError("");
    try {
      const nextSessions = await apiClient.listSessions();
      setSessions(nextSessions);
      const targetSessionId = selectSessionId ?? session?.id ?? nextSessions[0]?.id;
      if (!targetSessionId) {
        setSession(null);
        return;
      }
      const nextSession = await apiClient.getSession(targetSessionId);
      setSession(nextSession ?? null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to load sessions.");
    }
  }

  async function syncSession(sessionId: string) {
    const nextSession = await apiClient.getSession(sessionId);
    if (nextSession) {
      setSession(nextSession);
    }
  }

  function resetCaptureDraft() {
    setBoardFile(null);
    setBoardCorners([]);
  }

  async function handleCreateSession() {
    setBusy(true);
    setError("");
    try {
      const nextSession = await apiClient.createSession(sessionTitle || undefined);
      setSession(nextSession);
      setSessionTitle("");
      setStatusMessage(`Created ${nextSession.label}.`);
      await loadSessions(nextSession.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to create session.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveBoardCapture() {
    if (!session || !boardFile) {
      setError("Choose a session and upload a photo first.");
      return;
    }
    if (captureKind === "board" && boardCorners.length !== 4) {
      setError("Board photos need exactly four corner taps.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const nextSession = await apiClient.saveBoardCapture(session.id, {
        file: boardFile,
        fileName: boardFile.name,
        previewUrl: boardPreview,
        kind: captureKind,
        boardCorners: captureKind === "board" ? boardCorners : [],
        replaceCurrent: true,
      });
      setSession(nextSession);
      setStatusMessage(
        `Saved ${captureLabel(captureKind).toLowerCase()} v${nextSession.boardCapture?.version ?? "?"}.`
      );
      resetCaptureDraft();
      await loadSessions(nextSession.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to save capture.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitGapQuery() {
    if (!session || !selectedGapBoardCapture || gapTap.length !== 1) {
      setError("Choose a board photo for the gap and tap exactly one target gap.");
      return;
    }
    const selectedCaptureIds = [...selectedCandidateCaptureIds];
    if (selectedCaptureIds.length === 0) {
      setError("Select at least one capture to search for candidate pieces.");
      return;
    }
    setBusy(true);
    setError("");

    const manualCorrection: ManualCorrection | null =
      manualExtraTap.length || manualPolygon.length
        ? {
            extraTap: manualExtraTap[0] ?? null,
            polygon: manualPolygon,
          }
        : null;

    const request: GapQueryRequest = {
      boardCaptureId: selectedGapBoardCapture.boardCaptureId,
      candidateCaptureIds: selectedCaptureIds,
      gapTap: gapTap[0],
      gapImage: gapFile ?? undefined,
      gapCloseupUrl: gapPreview || undefined,
      manualCorrection,
    };

    try {
      const rawResult = await apiClient.submitGapQuery(session.id, request);
      const filteredCandidates = rawResult.candidates.filter(
        (candidate) =>
          !candidate.sourceBoardCaptureId ||
          selectedCaptureIds.includes(candidate.sourceBoardCaptureId)
      );
      const filteredPrompts = rawResult.pieceScanPrompts.filter((prompt) =>
        filteredCandidates.some((candidate) => candidate.id === prompt.candidateId)
      );
      const result: QueryResult = {
        ...rawResult,
        candidates: filteredCandidates,
        pieceScanPrompts: filteredPrompts,
      };
      setSession((current) =>
        current
          ? {
              ...current,
              queryCount: current.queryCount + 1,
              lastQuery: result,
            }
          : current
      );
      setSelectedCandidateId(result.candidates[0]?.id ?? "");
      setStatusMessage(
        `${result.summary} Searched ${selectedCaptureIds.length} capture${selectedCaptureIds.length === 1 ? "" : "s"}.`
      );
      await syncSession(session.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to submit gap query.");
    } finally {
      setBusy(false);
    }
  }

  async function handlePieceScanVerification() {
    if (!session || !activeQuery || pieceFiles.length === 0) {
      setError("Choose a query and attach at least one piece scan.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      let result: QueryResult | null = null;
      for (const file of pieceFiles) {
        const request: PieceScanRequest = {
          queryId: activeQuery.queryId,
          candidateId: selectedCandidateId || activeQuery.candidates[0]?.id || "",
          file,
        };
        result = await apiClient.submitPieceScan(session.id, request);
      }
      if (result) {
        setSession((current) =>
          current
            ? {
                ...current,
                lastQuery: result,
              }
            : current
        );
        setStatusMessage("Close-up verification complete.");
      }
      await syncSession(session.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to upload piece scans.");
    } finally {
      setBusy(false);
    }
  }

  function toggleCandidateCapture(captureId: string) {
    setSelectedCandidateCaptureIds((current) =>
      current.includes(captureId)
        ? current.filter((value) => value !== captureId)
        : [...current, captureId]
    );
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <article className="hero-card">
          <p className="hero-label">LAN mobile assistant</p>
          <h1>Capture, tap, verify.</h1>
          <p className="hero-copy">
            Save one board photo for the gap, then add as many loose-piece overview photos as needed.
            Every match now points back to the exact capture and region it came from.
          </p>
        </article>
        <article className="hero-card">
          <p className="eyebrow">Status</p>
          <StatusPill state={mapConfidenceState(activeQuery?.confidence)}>
            {activeQuery?.confidence ?? "waiting"}
          </StatusPill>
          <p className="hero-copy">{statusMessage}</p>
          {error ? <p className="warning">{error}</p> : null}
        </article>
      </section>

      <section className="panel-grid panel-grid-tight">
        <article className="panel">
          <div className="panel-heading">
            <h2>Session control</h2>
            <StatusPill state={session ? "complete" : "pending"}>
              {session ? "active" : "idle"}
            </StatusPill>
          </div>

          <label className="field">
            <span>New session title</span>
            <input
              onChange={(event) => setSessionTitle(event.target.value)}
              placeholder="Weekend white puzzle"
              value={sessionTitle}
            />
          </label>

          <div className="actions-row">
            <button className="action-button" disabled={busy} onClick={() => void handleCreateSession()} type="button">
              Create session
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => void loadSessions()} type="button">
              Refresh sessions
            </button>
          </div>

          <label className="field">
            <span>Open existing session</span>
            <select
              onChange={(event) => {
                if (event.target.value) {
                  void loadSessions(event.target.value);
                }
              }}
              value={session?.id ?? ""}
            >
              <option value="">Select a session</option>
              {sessions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <dl className="meta-list">
            <div>
              <dt>Session id</dt>
              <dd>{session?.id ?? "Not selected"}</dd>
            </div>
            <div>
              <dt>Saved captures</dt>
              <dd>{session?.boardRevisionCount ?? 0}</dd>
            </div>
            <div>
              <dt>Queries</dt>
              <dd>{session?.queryCount ?? 0}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Add capture</h2>
            <StatusPill state={session ? "complete" : "pending"}>
              {session ? "ready" : "missing session"}
            </StatusPill>
          </div>

          <label className="field">
            <span>Capture type</span>
            <select
              onChange={(event) => {
                setCaptureKind(event.target.value as CaptureKind);
                setBoardCorners([]);
              }}
              value={captureKind}
            >
              <option value="board">Board photo with puzzle</option>
              <option value="pieces">Loose-piece overview</option>
            </select>
          </label>

          <label className="file-field">
            <span>{captureKind === "board" ? "Board photo" : "Loose-piece overview photo"}</span>
            <input
              accept="image/*"
              capture="environment"
              onChange={(event) => setBoardFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>

          {boardPreview ? (
            captureKind === "board" ? (
              <ImageTapTarget
                imageUrl={boardPreview}
                labels={["TL", "TR", "BR", "BL"]}
                maxPoints={4}
                onChange={setBoardCorners}
                points={boardCorners}
                title="Tap board corners in clockwise order"
              />
            ) : (
              <div className="capture-preview">
                <img alt="Loose-piece overview preview" src={boardPreview} />
              </div>
            )
          ) : (
            <p className="hint">
              Save one board photo for the assembled puzzle, then add extra loose-piece overviews as needed.
            </p>
          )}

          <div className="actions-row">
            <button className="action-button" disabled={busy || !session} onClick={() => void handleSaveBoardCapture()} type="button">
              Save capture
            </button>
            <button className="secondary-button" onClick={() => setBoardCorners([])} type="button">
              Clear corners
            </button>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Saved captures</h2>
          <StatusPill state={boardCaptures.length ? "complete" : "pending"}>
            {boardCaptures.length ? `${boardCaptures.length} saved` : "none"}
          </StatusPill>
        </div>

        {boardCaptures.length ? (
          <div className="capture-list">
            {boardCaptures.map((capture) => (
              <article className="capture-card" key={capture.boardCaptureId}>
                <div className="capture-card-header">
                  <div>
                    <h3>{captureLabel(capture.kind)} v{capture.version}</h3>
                    <p>{capture.fileName}</p>
                  </div>
                  <StatusPill state={capture.kind === "board" ? "complete" : "pending"}>
                    {capture.kind}
                  </StatusPill>
                </div>
                <div className="capture-preview small">
                  <img alt={capture.fileName} src={capture.previewUrl} />
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="hint">No captures saved in this session yet.</p>
        )}
      </section>

      <section className="panel-grid panel-grid-tight">
        <article className="panel">
          <div className="panel-heading">
            <h2>Gap query</h2>
            <StatusPill state={activeQuery ? mapConfidenceState(activeQuery.confidence) : "pending"}>
              {activeQuery ? activeQuery.confidence : "waiting"}
            </StatusPill>
          </div>

          <label className="field">
            <span>Board photo that contains the gap</span>
            <select
              onChange={(event) => setSelectedGapBoardCaptureId(event.target.value)}
              value={selectedGapBoardCaptureId}
            >
              <option value="">Select a board photo</option>
              {gapBoardOptions.map((capture) => (
                <option key={capture.boardCaptureId} value={capture.boardCaptureId}>
                  Board v{capture.version} · {capture.fileName}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="capture-filter">
            <legend>Search candidate pieces in these captures</legend>
            {boardCaptures.map((capture) => (
              <label className="checkbox-row" key={capture.boardCaptureId}>
                <input
                  checked={selectedCandidateCaptureIds.includes(capture.boardCaptureId)}
                  onChange={() => toggleCandidateCapture(capture.boardCaptureId)}
                  type="checkbox"
                />
                <span>
                  {capture.kind === "board" ? "Board" : "Pieces"} v{capture.version} · {capture.fileName}
                </span>
              </label>
            ))}
          </fieldset>

          <label className="file-field">
            <span>Optional gap close-up</span>
            <input
              accept="image/*"
              capture="environment"
              onChange={(event) => setGapFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>

          {activeBoardImage ? (
            <ImageTapTarget
              imageUrl={activeBoardImage}
              labels={["Gap"]}
              maxPoints={1}
              onChange={setGapTap}
              points={gapTap}
              title="Tap the target interior gap"
            />
          ) : null}

          {activeGapImage ? (
            <>
              <ImageTapTarget
                imageUrl={activeGapImage}
                labels={["Extra"]}
                maxPoints={1}
                onChange={setManualExtraTap}
                points={manualExtraTap}
                title="Optional rescue tap if extraction misses"
              />
              <ImageTapTarget
                imageUrl={activeGapImage}
                maxPoints={8}
                onChange={setManualPolygon}
                points={manualPolygon}
                title="Optional correction polygon"
              />
            </>
          ) : null}

          <div className="actions-row">
            <button className="action-button" disabled={busy || !selectedGapBoardCapture} onClick={() => void handleSubmitGapQuery()} type="button">
              Rank candidates
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                setGapTap([]);
                setManualExtraTap([]);
                setManualPolygon([]);
              }}
              type="button"
            >
              Clear query taps
            </button>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Verification</h2>
            <StatusPill state={activeQuery?.pieceScanPrompts.length ? "warning" : "pending"}>
              {activeQuery?.pieceScanPrompts.length ? "scan requested" : "standby"}
            </StatusPill>
          </div>

          <label className="field compact-field">
            <span>Candidate to verify</span>
            <select
              onChange={(event) => setSelectedCandidateId(event.target.value)}
              value={selectedCandidateId}
            >
              <option value="">Use the full shortlist</option>
              {(activeQuery?.candidates ?? []).map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.label}
                </option>
              ))}
            </select>
          </label>

          <label className="file-field">
            <span>Piece scan images</span>
            <input
              accept="image/*"
              capture="environment"
              multiple
              onChange={(event) => setPieceFiles(Array.from(event.target.files ?? []))}
              type="file"
            />
          </label>

          <div className="actions-row">
            <button className="action-button" disabled={busy || !activeQuery} onClick={() => void handlePieceScanVerification()} type="button">
              Upload verification scans
            </button>
          </div>

          {activeQuery?.pieceScanPrompts.length ? (
            <div className="prompt-strip">
              {activeQuery.pieceScanPrompts.map((prompt) => (
                <article className="prompt-card" key={prompt.candidateId}>
                  <h3>{prompt.label}</h3>
                  <p>{prompt.message}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="hint">Verification prompts will appear when ranking confidence is conservative.</p>
          )}
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Candidate shortlist</h2>
          <StatusPill state={activeQuery?.needsManualCorrection ? "warning" : "pending"}>
            {activeQuery?.needsManualCorrection ? "manual correction suggested" : "latest results"}
          </StatusPill>
        </div>

        {activeQuery ? (
          <>
            <p className="result-summary">{activeQuery.summary}</p>
            <div className="candidate-grid">
              {activeQuery.candidates.map((candidate) => (
                <CandidateCard
                  candidate={candidate}
                  key={candidate.id}
                  session={session}
                  selected={candidate.id === selectedCandidateId}
                  onSelect={() => setSelectedCandidateId(candidate.id)}
                />
              ))}
            </div>
          </>
        ) : (
          <p className="hint">No query has been run yet.</p>
        )}
      </section>
    </main>
  );
}


function CandidateCard({
  candidate,
  onSelect,
  selected,
  session,
}: {
  candidate: MatchCandidate;
  onSelect: () => void;
  selected: boolean;
  session: BoardSession | null;
}) {
  const sourceCapture = session?.boardCaptures.find(
    (capture) => capture.boardCaptureId === candidate.sourceBoardCaptureId
  );

  return (
    <button
      className="candidate-card"
      onClick={onSelect}
      style={selected ? { outline: "2px solid #1f3a4d" } : undefined}
      type="button"
    >
      <div className="candidate-card-header">
        <div>
          <h3>{candidate.label}</h3>
          <p>{Math.round(candidate.score * 100)}% match</p>
        </div>
        <StatusPill state={mapConfidenceState(candidate.confidence)}>
          {candidate.confidence}
        </StatusPill>
      </div>

      <CandidatePreview candidate={candidate} sourceImageUrl={sourceCapture?.previewUrl} />

      <dl className="meta-list compact-meta">
        <div>
          <dt>Where to look</dt>
          <dd>
            {sourceCapture
              ? `${captureLabel(sourceCapture.kind)} v${sourceCapture.version}`
              : "Unknown source capture"}
          </dd>
        </div>
        <div>
          <dt>Capture file</dt>
          <dd>{sourceCapture?.fileName ?? "Unavailable"}</dd>
        </div>
        {candidate.bbox ? (
          <div>
            <dt>Grid cell</dt>
            <dd>{gridCellLabel(candidate) ?? "Unknown"}</dd>
          </div>
        ) : null}
        {candidate.bbox ? (
          <div>
            <dt>Region start</dt>
            <dd>{formatPercent({ x: candidate.bbox.x, y: candidate.bbox.y })}</dd>
          </div>
        ) : null}
      </dl>

      <ul className="reason-list">
        {candidate.reasonCodes.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </button>
  );
}


function CandidatePreview({
  candidate,
  sourceImageUrl,
}: {
  candidate: MatchCandidate;
  sourceImageUrl?: string;
}) {
  if (!sourceImageUrl || !candidate.bbox) {
    return <div className="candidate-preview placeholder">No preview crop available yet.</div>;
  }

  const cell = gridCellLabel(candidate);

  return (
    <div className="candidate-preview">
      <img alt={candidate.label} src={sourceImageUrl} />
      <div className="candidate-grid-overlay">
        {Array.from({ length: GRID_COLUMNS - 1 }, (_, index) => (
          <span
            className="candidate-grid-line vertical"
            key={`v-${index}`}
            style={{ left: `${((index + 1) / GRID_COLUMNS) * 100}%` }}
          />
        ))}
        {Array.from({ length: GRID_ROWS - 1 }, (_, index) => (
          <span
            className="candidate-grid-line horizontal"
            key={`h-${index}`}
            style={{ top: `${((index + 1) / GRID_ROWS) * 100}%` }}
          />
        ))}
        <span
          className="candidate-highlight"
          style={{
            left: `${candidate.bbox.x * 100}%`,
            top: `${candidate.bbox.y * 100}%`,
            width: `${candidate.bbox.width * 100}%`,
            height: `${candidate.bbox.height * 100}%`,
          }}
        />
        {cell ? <span className="candidate-cell-badge">{cell}</span> : null}
      </div>
    </div>
  );
}


export default App;
