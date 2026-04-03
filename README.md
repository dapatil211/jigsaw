# Jigsaw Assistant

This repository is organized for a mobile-first jigsaw assistant that helps solve an all-white, random-cut puzzle from tabletop photos. The phone captures images, and a laptop-hosted backend performs the heavier geometric vision work.

## Repository Layout

```text
.
|-- PLAN.md
|-- README.md
|-- docs/
|   |-- TASKS.md
|   `-- capture-protocol.md
|-- frontend/
|   |-- package.json
|   |-- tsconfig.json
|   |-- vite.config.ts
|   |-- index.html
|   `-- src/
|       |-- App.tsx
|       |-- main.tsx
|       |-- styles.css
|       `-- types.ts
|-- backend/
|   |-- pyproject.toml
|   `-- app/
|       |-- main.py
|       |-- api/routes/sessions.py
|       |-- models/schemas.py
|       `-- services/
|           |-- storage.py
|           `-- vision.py
|-- data/
|   `-- README.md
`-- scripts/
    `-- README.md
```

## Project Shape

- `frontend/`: mobile web app / PWA for capture, taps, and result review
- `backend/`: FastAPI service for sessions, image ingestion, and vision pipelines
- `docs/`: planning, task tracking, and capture protocol
- `data/`: local sample data, evaluation manifests, and runtime session artifacts
- `scripts/`: helper scripts for dataset validation, setup, and evaluation

## Current Status

The baseline implementation now includes:

- persistent file-backed sessions on the backend
- board capture upload and versioning
- gap query submission with optional manual correction
- close-up piece scan verification
- heuristic contour-based ranking tuned for top-5 usefulness
- mobile web UI with LAN API integration and mock fallback
- manifest validation and offline baseline evaluation scripts

## Development Commands

Use the top-level [Makefile](/Users/darshanpatil/puzzles/Makefile) for the common local workflows:

```bash
make backend-install
make frontend-install
make backend-dev
make frontend-dev
make frontend-build
make backend-check
uv run --project backend python scripts/generate_smoke_fixture.py
make validate-manifest MANIFEST=data/manifests/smoke-manifest.json
make evaluate-baseline MANIFEST=data/manifests/smoke-manifest.json
```

## Baseline Workflow

1. Start the backend on the laptop with `make backend-dev`.
2. Start the frontend with `make frontend-dev`.
3. Open the frontend from the phone browser on the same network.
4. Create a session, upload a board photo, and tap the four board corners.
5. Upload an optional gap close-up, tap the target gap, and review the ranked candidates.
6. If the results are uncertain, upload close-up piece scans to rerank the shortlist.

## Smoke Fixture

If you want a quick local sanity check before capturing real puzzle data:

1. Run `uv run --project backend python scripts/generate_smoke_fixture.py`.
2. Validate the generated manifest with `make validate-manifest MANIFEST=data/manifests/smoke-manifest.json`.
3. Run the heuristic evaluator with `make evaluate-baseline MANIFEST=data/manifests/smoke-manifest.json`.

## Documentation

- [PLAN.md](/Users/darshanpatil/puzzles/PLAN.md): original implementation plan
- [docs/TASKS.md](/Users/darshanpatil/puzzles/docs/TASKS.md): task tracker with implemented status
- [docs/capture-protocol.md](/Users/darshanpatil/puzzles/docs/capture-protocol.md): capture procedure
- [docs/dataset-manifest.md](/Users/darshanpatil/puzzles/docs/dataset-manifest.md): manifest format
- [docs/vision-baseline.md](/Users/darshanpatil/puzzles/docs/vision-baseline.md): vision heuristics
- [docs/calibration-guidance.md](/Users/darshanpatil/puzzles/docs/calibration-guidance.md): confidence policy
