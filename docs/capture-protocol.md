# Capture Protocol

This protocol implements T02 from the task list. It defines how to collect board captures, gap queries, candidate piece scans, and labeled manifests for evaluation.

## Encoded Assumptions

- Sessions are persistent and may span multiple solving sessions.
- Board recapture is allowed within the same session and creates a new board version.
- The app is LAN-only in v1.
- In-hand piece scans are acceptable for verification.
- If automatic gap extraction fails, the app may request one extra tap or a rough correction polygon.
- Touching loose-piece clusters are scored as uncertain candidates and typically trigger close-up verification.

## Overhead Board Capture

- Stand above the puzzle and include the entire active board plus nearby loose pieces.
- The four board corners must be visible enough to tap manually in the app.
- Moderate perspective distortion is acceptable; the backend rectifies the board from the tapped corners.
- Retake if the image is blurry, badly underexposed, or has glare over the current working region.
- Keep the phone as steady as practical when taking repeated captures for the same board state.

## Gap Query Capture

- Tap the target interior gap on the board image.
- If prompted, capture a close-up centered on that gap and its neighboring placed pieces.
- If extraction fails, add one extra tap or draw a rough polygon around the intended gap contour.
- Gap close-ups are recommended, but the baseline can fall back to the overhead image if needed.

## Candidate Piece Verification

- When the app requests verification, scan only the shortlisted pieces.
- In-hand scans are acceptable as long as fingers do not cover the contour.
- A neutral background is helpful but not required in v1.
- Candidate scans are used to rerank the shortlist rather than to discover all loose pieces from scratch.

## Dataset Manifest Format

Each manifest entry should include:

- `session_id`
- `board_image`
- `board_corners`
- `board_capture_id` if a later query references a non-latest board version
- `gap_tap`
- optional `gap_image`
- optional `manual_correction`
- `truth_candidate_id` or another human-truth identifier
- optional `candidate_scans`
- optional notes for glare, blur, touching-piece clusters, or other difficult conditions

See [dataset-manifest.md](/Users/darshanpatil/puzzles/docs/dataset-manifest.md) for the concrete JSON shape used by the validation and evaluation scripts.
