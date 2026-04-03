#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.schemas import BoardCapturePayload, GapQueryPayload, ManualCorrectionInput, Point  # noqa: E402
from app.services.vision import analyze_board_capture, analyze_gap_query  # noqa: E402


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def _make_point(data: dict) -> Point:
    return Point(x=float(data["x"]), y=float(data["y"]))


def _make_manual_correction(data: dict | None) -> ManualCorrectionInput | None:
    if not data:
        return None
    extra = data.get("extra_tap")
    polygon = [_make_point(point) for point in data.get("rough_polygon", [])]
    return ManualCorrectionInput(
        extra_tap=_make_point(extra) if extra else None,
        rough_polygon=polygon,
    )


def evaluate_manifest(path: Path) -> dict[str, float | int]:
    manifest = _load_manifest(path)
    board_payload = BoardCapturePayload(
        corners=[_make_point(point) for point in manifest["board_corners"]],
        replace_current=True,
    )
    board_image_path = (path.parent / manifest["board_image"]).resolve()
    board_analysis = analyze_board_capture(board_image_path, board_payload)

    class _BoardCaptureShim:
        board_capture_id = "eval-board"
        piece_proposals = board_analysis.piece_proposals

    total = 0
    top1 = 0
    top5 = 0
    failed = 0
    scan_needed = 0

    for query in manifest.get("queries", []):
        total += 1
        gap_payload = GapQueryPayload(
            tap=_make_point(query["gap_tap"]),
            gap_closeup_expected=bool(query.get("gap_image")),
            manual_correction=_make_manual_correction(query.get("manual_correction")),
        )
        gap_path = None
        if query.get("gap_image"):
            gap_path = (path.parent / query["gap_image"]).resolve()
        analysis = analyze_gap_query(board_image_path, gap_path, _BoardCaptureShim, gap_payload)
        if not analysis.candidates:
            failed += 1
            continue
        truth = query.get("truth_candidate_id")
        top_ids = [candidate.candidate_id for candidate in analysis.candidates]
        if analysis.candidates[0].needs_piece_scan:
            scan_needed += 1
        if truth and analysis.candidates[0].candidate_id == truth:
            top1 += 1
        if truth and truth in top_ids[:5]:
            top5 += 1

    return {
        "queries": total,
        "top1": top1,
        "top5": top5,
        "failed": failed,
        "needs_piece_scan": scan_needed,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: evaluate_baseline.py <manifest.json> [<manifest.json> ...]")
        return 1
    aggregate = {
        "queries": 0,
        "top1": 0,
        "top5": 0,
        "failed": 0,
        "needs_piece_scan": 0,
    }
    for manifest in argv[1:]:
        result = evaluate_manifest(Path(manifest))
        for key, value in result.items():
            aggregate[key] += value
    queries = max(aggregate["queries"], 1)
    print(
        json.dumps(
            {
                **aggregate,
                "top1_rate": round(aggregate["top1"] / queries, 4),
                "top5_rate": round(aggregate["top5"] / queries, 4),
                "failure_rate": round(aggregate["failed"] / queries, 4),
                "scan_rate": round(aggregate["needs_piece_scan"] / queries, 4),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
