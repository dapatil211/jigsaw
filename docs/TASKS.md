# Task Tracking Checklist

This checklist turns the plan into tracked execution work. Each item includes its dependency shape, whether it can run in parallel, what "done" means, and the main ambiguity that may still need a product or engineering decision.

## Milestone 0: Foundations

- [x] T01 Freeze API and data contracts
  - Priority: critical path
  - Parallel: no
  - Depends on: none
  - Effort: 1-2 days
  - Implementation details: define `BoardSession`, `GapQuery`, `PieceScan`, `MatchResult`; document coordinate spaces; specify image payloads, optional fields, and error responses.
  - Done when: frontend and backend can both compile against the same request/response schema.
  - Status notes: implemented in `backend/app/models/schemas.py`, `backend/app/api/routes/sessions.py`, and `frontend/src/types.ts`.
  - Encoded assumptions: persistent sessions, board recapture allowed, LAN-only API surface.

- [x] T02 Define capture protocol and dataset manifest
  - Priority: critical path
  - Parallel: yes, after T01
  - Depends on: T01
  - Effort: 1-2 days
  - Implementation details: write a repeatable capture guide for overhead shots, gap close-ups, and piece scans; define manifest fields for taps, images, transforms, and labels.
  - Done when: one labeled query can be captured end to end and validated from disk.
  - Status notes: implemented in `docs/capture-protocol.md`, `docs/dataset-manifest.md`, and `scripts/validate_manifest.py`.
  - Encoded assumptions: in-hand scans allowed, board recapture allowed, LAN-only v1.
  - Remaining ambiguity: required sample size for a trustworthy benchmark.

## Milestone 1: Repo and Service Skeleton

- [x] T03 Scaffold frontend app shell
  - Priority: high
  - Parallel: yes
  - Depends on: T01
  - Effort: 2-3 days
  - Implementation details: set up React + TypeScript + Vite; add camera capture views, image preview, corner tapping, gap tapping, and mocked result cards.
  - Done when: a phone can create a mock session and walk through the full UI flow with fake data.
  - Status notes: implemented in `frontend/src/App.tsx`, `frontend/src/api/`, and `frontend/src/components/`.
  - Encoded assumptions: browser-based mobile web app first, with fallback mock mode when the backend is unavailable.

- [x] T04 Scaffold backend service and storage
  - Priority: high
  - Parallel: yes
  - Depends on: T01
  - Effort: 2-3 days
  - Implementation details: set up FastAPI, session directories, artifact storage, schema validation, and stub endpoints that return deterministic mock responses.
  - Done when: the frontend can hit live local endpoints and store raw image payloads plus metadata.
  - Status notes: implemented in `backend/app/main.py`, `backend/app/api/routes/sessions.py`, and `backend/app/services/storage.py`.
  - Encoded assumptions: synchronous processing, persistent raw artifacts, no authentication for LAN-only v1.

- [x] T05 Add developer scripts and local run flow
  - Priority: medium
  - Parallel: yes
  - Depends on: T03, T04
  - Effort: 0.5-1 day
  - Implementation details: add boot scripts or commands for running frontend and backend together, plus a simple dataset validation entrypoint.
  - Done when: a new developer can boot the stack locally with documented commands.
  - Status notes: implemented with the top-level `Makefile`, `scripts/validate_manifest.py`, and `scripts/evaluate_baseline.py`.
  - Encoded assumptions: native local setup first, with `uv` for backend dependencies.

## Milestone 2: Vision Baseline

- [x] T06 Implement board rectification
  - Priority: critical path
  - Parallel: yes
  - Depends on: T02, T04
  - Effort: 2-4 days
  - Implementation details: compute a homography from four board-corner taps, normalize to canonical board coordinates, and preserve transform metadata for overlay projection.
  - Done when: the backend can output a rectified board image and map UI coordinates correctly in both directions.
  - Status notes: baseline rectification implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: board recapture is allowed instead of perfect cross-capture drift handling.

- [x] T07 Implement overhead normalization and loose-piece region proposals
  - Priority: high
  - Parallel: yes
  - Depends on: T06
  - Effort: 3-5 days
  - Implementation details: add glare-tolerant preprocessing, edge-friendly contrast normalization, and candidate region extraction for loose pieces and clusters.
  - Done when: visible loose pieces or piece clusters are indexed with masks, contours, and confidence values.
  - Status notes: baseline proposals and cluster detection implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: touching clusters are preserved as uncertain candidates and may trigger close-up scans.

- [x] T08 Implement gap extraction
  - Priority: critical path
  - Parallel: yes
  - Depends on: T02, T04
  - Effort: 3-5 days
  - Implementation details: combine the user gap tap with optional close-up imagery to extract one or more normalized target mating arcs.
  - Done when: the backend can return a stable target contour representation or a structured failure state.
  - Status notes: automatic extraction plus manual-correction override implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: one extra tap and optional rough polygon are permitted on failure.

## Milestone 3: Matching and Verification

- [x] T09 Build coarse contour descriptor pipeline
  - Priority: critical path
  - Parallel: partially
  - Depends on: T07, T08
  - Effort: 4-6 days
  - Implementation details: implement the first descriptor family for random-cut contours, such as curvature signatures and arc-length-normalized boundary profiles, and precompute descriptors for indexed piece regions.
  - Done when: the backend can compare a gap representation against overhead-visible piece candidates.
  - Status notes: radial contour-signature baseline implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: unresolved clusters remain rankable but are penalized and flagged for verification.

- [x] T10 Build coarse ranking engine
  - Priority: critical path
  - Parallel: yes, with T11 once input contracts are stable
  - Depends on: T09
  - Effort: 2-4 days
  - Implementation details: run orientation search, boundary complementarity scoring, geometric feasibility checks, and shortlist generation with confidence buckets.
  - Done when: the backend returns a top-N candidate list with scores and reason codes.
  - Status notes: top-5 oriented ranking, confidence buckets, and reason codes implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: top-5 usefulness is the optimization target.

- [x] T11 Build close-up piece verification
  - Priority: high
  - Parallel: yes
  - Depends on: T01, T04
  - Effort: 3-5 days
  - Implementation details: accept piece scans, segment higher-resolution contours, align against target arcs, and rerank the coarse shortlist.
  - Done when: scanned candidate pieces can materially improve ranking confidence and reorder results.
  - Status notes: single-scan reranking baseline implemented in `backend/app/services/vision.py`.
  - Encoded assumptions: one clear in-hand scan is sufficient for the baseline.

## Milestone 4: Product Loop

- [x] T12 Build results UI and feedback loop
  - Priority: high
  - Parallel: yes
  - Depends on: T03, T10
  - Effort: 2-4 days
  - Implementation details: show top candidates, confidence, overlays, scan prompts, accept/reject actions, and failure messaging.
  - Done when: a user can act on a result without reading logs or raw JSON.
  - Status notes: implemented in `frontend/src/App.tsx` with candidate cards, confidence pills, reason codes, scan prompts, and manual-correction states.
  - Encoded assumptions: explanatory reason codes are shown; same-session accept/reject learning is deferred.

- [x] T13 Integrate end-to-end mobile flow
  - Priority: critical path
  - Parallel: mostly no
  - Depends on: T03, T04, T10, T12
  - Effort: 2-4 days
  - Implementation details: connect camera capture to backend uploads, validate image compression, verify overlay transforms, and add retake flows.
  - Done when: a real phone can capture, query, and review results against the live backend on the local network.
  - Status notes: implemented through `frontend/src/api/httpClient.ts`, backend artifact serving, and the capture/query/verification flow in `frontend/src/App.tsx`.
  - Encoded assumptions: the backend base URL defaults to the current host on port `8000`, with a mock fallback client when the LAN backend is unavailable.

## Milestone 5: Evaluation and Hardening

- [x] T14 Build evaluation harness
  - Priority: high
  - Parallel: yes
  - Depends on: T02, T10
  - Effort: 2-3 days
  - Implementation details: run offline evaluation on labeled examples and report top-1, top-5, latency, extraction failures, and scan-request rate.
  - Done when: every ranking change can be measured against a fixed benchmark.
  - Status notes: implemented in `scripts/evaluate_baseline.py`.
  - Remaining ambiguity: minimum benchmark size needed before trusting small metric shifts.

- [x] T15 Calibrate confidence and scan prompts
  - Priority: medium
  - Parallel: yes
  - Depends on: T11, T12, T14
  - Effort: 1-3 days
  - Implementation details: tune thresholds so low-confidence cases prefer verification rather than bad certainty.
  - Done when: the app reliably asks for more information in ambiguous cases instead of overclaiming.
  - Status notes: implemented as documented threshold guidance in `docs/calibration-guidance.md`.
  - Encoded assumptions: top-5 usefulness takes precedence over minimizing extra scans.

- [x] T16 Polish docs and onboarding
  - Priority: medium
  - Parallel: yes
  - Depends on: T05, T13, T14
  - Effort: 1-2 days
  - Implementation details: document local setup, capture flow, evaluation flow, session storage, and known limitations.
  - Done when: another engineer can set up and test the system without guided help.
  - Status notes: updated in `README.md`, `docs/`, `scripts/`, and `data/README.md`.
  - Encoded assumptions: large raw datasets stay external to git by default.

## Recommended Parallel Bundles

- Bundle A:
  - T03 frontend shell
  - T04 backend scaffold
  - T02 capture protocol
- Bundle B:
  - T06 board rectification
  - T08 gap extraction
  - T14 evaluation harness bootstrap
- Bundle C:
  - T10 coarse ranking
  - T11 close-up verification
  - T12 results UI

## Immediate Next Tasks

- [ ] Capture and label the first 5-10 real gap queries.
- [ ] Run `scripts/evaluate_baseline.py` on that dataset and tune thresholds if needed.
- [ ] Decide whether to keep the mock frontend fallback once the LAN workflow is stable.
