#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def _validate_point(point: dict, context: str, errors: list[str]) -> None:
    for key in ("x", "y"):
        if key not in point:
            errors.append(f"{context}: missing `{key}`.")
            continue
        value = point[key]
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            errors.append(f"{context}: `{key}` must be a number in [0, 1].")


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return [f"{path}: failed to parse JSON: {exc}"]

    for key in ("session_id", "board_image", "board_corners", "queries"):
        if key not in data:
            errors.append(f"{path}: missing top-level `{key}`.")

    board_image = data.get("board_image")
    if isinstance(board_image, str):
        board_path = (path.parent / board_image).resolve()
        if not board_path.exists():
            errors.append(f"{path}: board image not found: {board_image}")

    corners = data.get("board_corners", [])
    if len(corners) != 4:
        errors.append(f"{path}: `board_corners` must contain exactly 4 points.")
    for index, corner in enumerate(corners):
        _validate_point(corner, f"{path}: board_corners[{index}]", errors)

    queries = data.get("queries", [])
    seen_query_ids: set[str] = set()
    for index, query in enumerate(queries):
        context = f"{path}: queries[{index}]"
        query_id = query.get("query_id")
        if not query_id:
            errors.append(f"{context}: missing `query_id`.")
        elif query_id in seen_query_ids:
            errors.append(f"{context}: duplicate query id `{query_id}`.")
        else:
            seen_query_ids.add(query_id)
        if "gap_tap" not in query:
            errors.append(f"{context}: missing `gap_tap`.")
        else:
            _validate_point(query["gap_tap"], f"{context}.gap_tap", errors)
        image_value = query.get("gap_image")
        if isinstance(image_value, str):
            image_path = (path.parent / image_value).resolve()
            if not image_path.exists():
                errors.append(f"{context}: gap_image not found: {image_value}")
        manual = query.get("manual_correction")
        if isinstance(manual, dict):
            if "extra_tap" in manual:
                _validate_point(manual["extra_tap"], f"{context}.manual_correction.extra_tap", errors)
            for poly_index, point in enumerate(manual.get("rough_polygon", [])):
                _validate_point(
                    point,
                    f"{context}.manual_correction.rough_polygon[{poly_index}]",
                    errors,
                )
        for scan_index, scan in enumerate(query.get("candidate_scans", [])):
            scan_context = f"{context}.candidate_scans[{scan_index}]"
            image = scan.get("image")
            if not image:
                errors.append(f"{scan_context}: missing `image`.")
            else:
                image_path = (path.parent / image).resolve()
                if not image_path.exists():
                    errors.append(f"{scan_context}: image not found: {image}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: validate_manifest.py <manifest.json> [<manifest.json> ...]")
        return 1
    all_errors: list[str] = []
    for manifest in argv[1:]:
        path = Path(manifest)
        if not path.exists():
            all_errors.append(f"{path}: file not found.")
            continue
        all_errors.extend(validate_manifest(path))
    if all_errors:
        print("\n".join(all_errors))
        return 1
    print(f"validated {len(argv) - 1} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
