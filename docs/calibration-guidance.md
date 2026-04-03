# Calibration Guidance

This document implements the T15 guidance for confidence calibration and scan-prompt behavior.

## Optimization Target

The system is tuned for top-5 usefulness, not top-1 certainty.

## Confidence Policy

- Promote to `high_confidence` only when the best candidate score is clearly above the baseline threshold and no additional uncertainty flags are present.
- Use `medium_confidence` when a candidate looks plausible but does not clearly dominate the shortlist.
- Use `needs_piece_scan` whenever:
  - the proposal is a touching-piece cluster
  - segmentation confidence is low
  - no gap close-up was provided and the match is only marginal
  - the score gap between top candidates is small

## Manual Correction Policy

- If gap extraction fails outright, request one extra tap or a rough polygon.
- If correction succeeds, preserve the `manual_correction_used` reason so the UI can communicate lower trust in the original automatic extraction.

## Initial Thresholds

- `high_confidence`: top score >= 0.86 and the best candidate is not a cluster
- `medium_confidence`: top score >= 0.72 and the leading candidates are not cluster-heavy
- Low extraction confidence: `failed_extraction`
- Otherwise: `needs_piece_scan`

These thresholds are intentionally conservative and should be tuned against labeled examples rather than anecdotal success.
