# Vision Baseline

This document covers T06-T11 from the task list and matches the implemented baseline in `backend/app/services/vision.py`.

## Implemented Flow

1. Rectify the board from four user-tapped corners.
2. Detect loose-piece region proposals outside the board polygon.
3. Extract a target contour for a selected gap from the overhead image or a gap close-up.
4. Compute contour signatures and rank visible piece proposals against the target.
5. Mark low-confidence and cluster candidates as needing close-up verification.
6. Rerank candidates when a close-up piece scan is provided.

## Encoded Assumptions

- Random-cut pieces are represented with generic contour signatures rather than a four-side model.
- Touching-piece clusters are not discarded; they are retained as uncertain candidates with a `requires_piece_scan` reason.
- The ranking baseline is deliberately conservative. Low-confidence cases prefer `needs_piece_scan`.
- Gap close-ups improve extraction confidence but are not mandatory for every query.
- Manual correction polygons override automatic gap extraction when provided.

## Known Limitations

- The coarse ranking compares full contour signatures, not true mating arcs.
- Cluster handling is intentionally cautious and may over-request close-up scans.
- Glare and poor separation can still reduce proposal quality.
- This is a baseline designed for usefulness and iteration, not final puzzle-solving accuracy.
