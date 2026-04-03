# Dataset Manifest

This document defines the JSON manifest consumed by `scripts/validate_manifest.py` and `scripts/evaluate_baseline.py`.

## Manifest Shape

```json
{
  "session_id": "session-example",
  "board_image": "data/raw/board-001.jpg",
  "board_corners": [
    { "x": 0.12, "y": 0.18 },
    { "x": 0.82, "y": 0.17 },
    { "x": 0.85, "y": 0.78 },
    { "x": 0.14, "y": 0.80 }
  ],
  "queries": [
    {
      "query_id": "query-001",
      "gap_tap": { "x": 0.46, "y": 0.52 },
      "gap_image": "data/raw/gap-001.jpg",
      "manual_correction": {
        "extra_tap": { "x": 0.48, "y": 0.51 },
        "rough_polygon": [
          { "x": 0.41, "y": 0.48 },
          { "x": 0.52, "y": 0.48 },
          { "x": 0.53, "y": 0.56 },
          { "x": 0.42, "y": 0.57 }
        ]
      },
      "truth_candidate_id": "proposal-007",
      "candidate_scans": [
        {
          "candidate_id": "proposal-007",
          "image": "data/raw/piece-007.jpg"
        }
      ],
      "notes": "Glare near lower-right quadrant."
    }
  ]
}
```

## Field Rules

- All points are normalized to `[0, 1]`.
- `board_corners` must contain exactly four points.
- `gap_image` is optional but recommended.
- `manual_correction` is optional and may contain either `extra_tap`, `rough_polygon`, or both.
- `truth_candidate_id` should match the candidate id expected from the board capture baseline whenever possible.
- `candidate_scans` may be empty if only coarse ranking is being evaluated.
