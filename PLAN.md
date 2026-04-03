# Jigsaw Assistant Plan

## Goal

Build a mobile-first jigsaw assistant that helps solve an all-white, random-cut puzzle from tabletop photos. The v1 system should run as a phone-friendly web app backed by a laptop-hosted vision service. The primary workflow is:

1. Capture an overhead photo of the puzzle and loose pieces.
2. Tap a target interior gap.
3. Get a ranked shortlist of likely matching pieces.
4. Optionally scan a few candidate pieces close-up to rerank them.

The target for v1 is a useful assistant, not a fully autonomous solver. Success means the correct piece is often in the top 5 suggestions within a few seconds.

## Architecture Summary

- Frontend: mobile web app / PWA usable from iPhone or Android
- Backend: Python service running on a laptop on the same local network
- Core approach: coarse-to-fine geometric matching
- Main signals: contours, gap boundaries, shape complementarity, geometric feasibility
- Non-goals for v1:
  - fully autonomous solving
  - texture-based matching
  - on-device-only inference
  - perfect segmentation of every touching loose piece from the overhead shot

## Parallelization Overview

### Critical Path

These steps gate most downstream work and should happen first:

1. Freeze API and data contracts.
2. Define the capture protocol and create an evaluation dataset.
3. Build board rectification and gap extraction.
4. Build coarse candidate ranking.
5. Add close-up verification and integrate end to end.

### Parallel Tracks

Once the contracts are fixed, these can proceed in parallel:

- Frontend app shell and capture UX
- Backend service scaffolding and session storage
- Vision R&D on segmentation and contour descriptors
- Dataset tooling and evaluation harness

Once coarse ranking is stable, these can also proceed in parallel:

- Close-up piece verification
- Results UI and feedback loop
- Confidence calibration and failure-mode handling

## Work Plan

### 1. Freeze v1 data model and API contracts

**Objective**

Define the exact request/response shape and coordinate systems so frontend and backend can move independently.

**Implementation details**

- Define core entities:
  - `BoardSession`
  - `GapQuery`
  - `PieceScan`
  - `MatchResult`
- Define API endpoints:
  - `POST /sessions`
  - `POST /sessions/{id}/board-capture`
  - `POST /sessions/{id}/gap-query`
  - `POST /sessions/{id}/piece-scan`
  - `GET /sessions/{id}/queries/{qid}`
- Specify coordinate spaces explicitly:
  - raw image coordinates
  - rectified board coordinates
  - UI overlay coordinates
- Define what is required vs optional in each request:
  - overhead board image
  - 4 board-corner taps
  - tapped gap location
  - optional gap close-up
  - optional candidate piece close-up
- Define confidence states:
  - `high_confidence`
  - `medium_confidence`
  - `needs_piece_scan`
  - `failed_extraction`

**Subtasks**

- Write TypeScript and Python schema definitions.
- Document image payload formats and compression expectations.
- Define how derived artifacts are referenced in responses.
- Decide error response shapes for bad captures and failed extraction.

**Can run in parallel?**

- No. This is the main blocker for the rest of the implementation.

**Ambiguities to decide**

- Whether sessions are disposable or persisted across days.
- Whether the overhead board image can be replaced mid-session.
- Whether the app is LAN-only for v1 or needs a remote-friendly contract.

### 2. Define the capture protocol and benchmark dataset

**Objective**

Create a repeatable input format and a labeled dataset for evaluating improvements.

**Implementation details**

- Write a capture guide for:
  - overhead board shots
  - gap close-ups
  - candidate piece scans
- Define expected camera distance, angle tolerance, and retake conditions.
- Store a manifest for each labeled query with:
  - source images
  - board corner taps
  - gap tap
  - optional gap crop
  - candidate scans
  - ground-truth matching piece
- Organize sample data so offline evaluation can run without the UI.

**Subtasks**

- Draft the capture protocol.
- Collect an initial labeled set of gap queries.
- Build a manifest schema for image sets and labels.
- Create a small script to validate dataset completeness.

**Can run in parallel?**

- Yes, after step 1.
- Can proceed in parallel with frontend/backend scaffolding.

**Ambiguities to decide**

- How many labeled examples are enough for a useful v1 benchmark.
- Whether piece scans happen in-hand or on the table.
- Whether the board is assumed static between captures.

### 3. Build the mobile web app shell

**Objective**

Create the phone-facing UI for capture, tapping, uploading, and viewing ranked candidates.

**Implementation details**

- Use a mobile-first React + TypeScript app.
- Support:
  - session creation
  - in-app camera capture
  - image preview and retake
  - board corner tapping
  - gap tapping
  - result overlays on the board image
  - candidate review and piece-scan flow
- Start with mocked API responses so the UI can be built before vision is ready.
- Ensure touch interactions work on small screens:
  - pinch/zoom
  - pan
  - tap precision

**Subtasks**

- Scaffold the frontend project.
- Implement session and capture screens.
- Implement tap/overlay image component.
- Build mock result cards and candidate review UI.
- Connect to real backend endpoints once available.

**Can run in parallel?**

- Yes, after step 1.
- Independent of most vision work if mocks are used first.

**Ambiguities to decide**

- Whether v1 should be PWA-installable or only browser-based.
- Whether offline capture queues are needed.
- How much gesture support is required for precise gap selection.

### 4. Build the backend service and storage layer

**Objective**

Stand up the laptop-hosted service that receives images, stores session state, and runs vision jobs.

**Implementation details**

- Use FastAPI.
- Start with file-backed session storage:
  - raw images
  - derived artifacts
  - JSON metadata
  - processing logs
- Keep processing synchronous first to simplify debugging.
- Expose a small, stable API surface aligned with step 1.

**Subtasks**

- Scaffold the backend project and dependency management.
- Implement session creation and artifact storage.
- Add endpoint handlers and response models.
- Add logging and request tracing for debugging image issues.

**Can run in parallel?**

- Yes, after step 1.
- Can run in parallel with frontend and dataset work.

**Ambiguities to decide**

- Whether to retain all raw images by default.
- Whether background jobs are needed for long-running processing.
- Whether any authentication is needed for LAN usage.

### 5. Implement board rectification and overhead indexing

**Objective**

Turn the overhead photo into a normalized board view and a rough index of visible loose pieces.

**Implementation details**

- Compute a homography from the 4 user-tapped board corners.
- Rectify the board into a canonical coordinate frame.
- Apply lighting normalization and glare suppression.
- Detect candidate loose-piece regions outside the assembled area.
- Store region proposals with:
  - masks
  - contours
  - bounding boxes
  - confidence scores
- Allow low-confidence clusters to remain as unresolved groups instead of forcing bad segmentation.

**Subtasks**

- Implement perspective correction.
- Implement contrast normalization / glare mitigation.
- Implement loose-piece region proposal extraction.
- Export piece-region descriptors for downstream ranking.

**Can run in parallel?**

- Yes, after steps 1 and 2.
- Can proceed in parallel with gap extraction.

**Ambiguities to decide**

- How aggressively to split touching-piece clusters.
- Whether clustered regions are usable for coarse ranking or must be skipped.
- How often the user must refresh board-corner taps if the phone angle changes.

### 6. Implement gap extraction from close-up images

**Objective**

Extract a reliable geometric target representation for the selected interior gap.

**Implementation details**

- Use the tapped gap location to anchor extraction.
- Accept an optional close-up image for higher-quality boundary recovery.
- Segment the gap and neighboring placed-piece boundaries.
- Convert the gap boundary into one or more candidate mating arcs.
- Normalize for local scale and orientation.

**Subtasks**

- Build gap crop generation from the overhead and close-up images.
- Implement gap-boundary segmentation.
- Derive normalized contour features for matching.
- Add extraction diagnostics for failed or low-confidence cases.

**Can run in parallel?**

- Yes, after step 1.
- Largely independent of overhead loose-piece indexing.

**Ambiguities to decide**

- Whether the user may supply an extra tap or rough correction if extraction fails.
- Whether close-up images are required or merely recommended for some queries.
- How to represent gaps with multiple irregular contact arcs.

### 7. Build the coarse candidate ranking engine

**Objective**

Produce a shortlist of likely matching pieces from the overhead board state and extracted gap geometry.

**Implementation details**

- Model pieces and gaps as arbitrary random-cut contours, not four-sided puzzle pieces.
- Compute contour descriptors such as:
  - curvature signatures
  - arc-length-normalized boundary profiles
  - local extrema / notch-tab analogs
- Score each candidate using:
  - boundary complementarity
  - scale consistency
  - orientation search
  - physical feasibility
- Return top-N candidates with confidence scores and reasons.

**Subtasks**

- Choose the first descriptor family to implement.
- Precompute piece descriptors from overhead-indexed regions.
- Implement gap-to-piece scoring.
- Build shortlist generation and result serialization.

**Can run in parallel?**

- Yes, after steps 5 and 6.
- Can run in parallel with close-up verification if contracts are stable.

**Ambiguities to decide**

- Which descriptor family should be the initial baseline.
- How large the coarse shortlist should be.
- Whether unresolved clusters can contribute partial candidate evidence.

### 8. Build the close-up piece verification pipeline

**Objective**

Improve ranking accuracy by rescoring a small number of user-scanned candidate pieces.

**Implementation details**

- Accept 3 to 10 candidate scans from the phone.
- Extract high-resolution contours from each scanned piece.
- Search over rotation and translation to test fit against the target gap arcs.
- Produce refined scores and updated ranking.
- Prefer this stage over overconfident guesses when coarse ranking is weak.

**Subtasks**

- Implement close-up piece segmentation.
- Implement rigid alignment / search over orientations.
- Add higher-fidelity shape compatibility scoring.
- Merge coarse and refined scores into a single reranked result.

**Can run in parallel?**

- Yes, after step 1.
- Practical backend work can start after the `PieceScan` contract is fixed.

**Ambiguities to decide**

- What scan background is acceptable for in-hand piece capture.
- Whether multiple angles or a single scan per piece are sufficient.
- How many verification scans are acceptable before the UX feels too slow.

### 9. Build the results UI and interaction loop

**Objective**

Make the assistant usable as a decision-support tool during real puzzle solving.

**Implementation details**

- Show:
  - top 5 candidates
  - overlay locations on the overhead image
  - confidence bucket
  - prompts for which candidates to scan next
- Record user actions:
  - accepted suggestion
  - rejected suggestion
  - scan requested
  - extraction failed
- Surface low-confidence states clearly instead of pretending certainty.

**Subtasks**

- Design result cards and overlay states.
- Implement scan-next prompts for ambiguous queries.
- Add feedback capture for accepted/rejected suggestions.
- Add error and retry flows for failed captures.

**Can run in parallel?**

- Yes, once result schemas are stable.
- Can proceed in parallel with ranking and verification work.

**Ambiguities to decide**

- Whether user feedback should affect ranking within the same session.
- Whether the UI should explain why a candidate was suggested.
- How much history of past queries should be visible.

### 10. Build the evaluation harness and calibration loop

**Objective**

Measure whether the assistant is actually useful and tune it toward top-5 success.

**Implementation details**

- Run offline evaluation against the labeled dataset.
- Track:
  - top-1 accuracy
  - top-5 accuracy
  - latency
  - piece-scan request rate
  - extraction failure rate
- Save intermediate artifacts for failure analysis.
- Calibrate thresholds so the system requests more scans when confidence is low.

**Subtasks**

- Implement evaluation scripts.
- Add reproducible metrics reporting.
- Build a corpus of failure cases and representative examples.
- Tune confidence buckets and scan-request thresholds.

**Can run in parallel?**

- Yes, once the dataset and at least one ranking path exist.
- Continues in parallel throughout development.

**Ambiguities to decide**

- Whether the main optimization target is top-5 usefulness, fewer scans, or lower latency.
- What minimum dataset size is required before trusting metric changes.
- How aggressively to optimize for hard failure avoidance versus precision.

### 11. Integrate the end-to-end phone-to-laptop workflow

**Objective**

Connect the mobile UI to the backend and validate the full solve loop on a real device.

**Implementation details**

- Wire the frontend to live endpoints.
- Handle image compression, upload progress, and retries.
- Validate coordinate transforms between the original image, rectified board, and UI overlays.
- Add quality checks for blurry or glare-heavy captures.
- Confirm local-network discovery or explicit backend configuration.

**Subtasks**

- Connect frontend API client to real backend.
- Validate all upload/download flows on a phone.
- Debug overlay alignment and transform errors.
- Add retake prompts for poor image quality.

**Can run in parallel?**

- Mostly no. This is a late-stage integration step.

**Ambiguities to decide**

- Whether backend discovery is automatic or manual.
- Whether to support image uploads over unstable local Wi-Fi.
- Whether partial functionality should remain available if some derived artifacts fail.

### 12. Package the repo for development and iteration

**Objective**

Make the project easy to run, extend, and evaluate.

**Implementation details**

- Create a clean repo layout:
  - `frontend/`
  - `backend/`
  - `data/` or external dataset path
  - `docs/`
- Pin dependencies and add setup instructions.
- Document:
  - developer setup
  - capture protocol
  - dataset format
  - evaluation workflow
  - local phone-to-laptop setup

**Subtasks**

- Choose package management for frontend and backend.
- Add local run scripts.
- Add environment configuration examples.
- Document expected hardware and network setup.

**Can run in parallel?**

- Partly.
- Basic layout and scripts can start early; final docs should be finished after integration stabilizes.

**Ambiguities to decide**

- Whether to use Docker or native local setup for v1.
- Whether sample images belong in the repo.
- Whether evaluation data should be versioned or stored externally.

## Suggested Initial Dependency Set

### Frontend

- React
- TypeScript
- Vite
- PWA plugin

### Backend

- FastAPI
- Uvicorn
- NumPy
- OpenCV
- SciPy
- scikit-image
- Pydantic

### Optional later

- Shapely for geometry utilities
- NetworkX if graph-style ranking becomes useful
- PyTorch only if a learned reranker becomes necessary

## Recommended Team Execution Order

If one engineer is working alone:

1. Step 1
2. Step 2
3. Steps 4, 5, and 6
4. Step 7
5. Steps 3 and 9
6. Step 8
7. Steps 10, 11, and 12

If multiple engineers are available:

- Engineer A: steps 1, 4, 11
- Engineer B: steps 5, 6, 7, 8
- Engineer C: steps 3 and 9
- Engineer D: steps 2, 10, 12

## Highest-Impact Open Decisions

- Whether sessions are short-lived or persistent across multiple puzzle sessions.
- Whether failed segmentation may ask for limited manual correction.
- What piece-scan conditions are acceptable in practice.
- How to treat unresolved touching-piece clusters in the overhead image.
- Whether the primary optimization target is top-5 usefulness, fewer scans, or lower latency.
