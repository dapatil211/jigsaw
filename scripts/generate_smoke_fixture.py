#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "smoke"
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"


def make_board_image() -> np.ndarray:
    image = np.full((1200, 1200, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (250, 250), (950, 950), (215, 215, 215), -1)

    for row in range(4):
        for column in range(4):
            x = 80 + column * 130
            y = 60 + row * 130
            points = np.array(
                [[x, y], [x + 45, y + 10], [x + 55, y + 50], [x + 15, y + 60], [x - 5, y + 30]],
                dtype=np.int32,
            )
            cv2.fillPoly(image, [points], (30, 30, 30))

    for row in range(3):
        for column in range(4):
            x = 980 + column * 45
            y = 120 + row * 160
            points = np.array(
                [[x, y], [x + 35, y + 5], [x + 40, y + 35], [x + 8, y + 45], [x - 5, y + 20]],
                dtype=np.int32,
            )
            cv2.fillPoly(image, [points], (50, 50, 50))

    return image


def make_gap_image() -> np.ndarray:
    image = np.full((320, 320, 3), 240, dtype=np.uint8)
    cv2.rectangle(image, (96, 96), (224, 224), (40, 40, 40), 2)
    return image


def make_piece_image() -> np.ndarray:
    image = np.full((220, 220, 3), 255, dtype=np.uint8)
    points = np.array([[60, 40], [150, 55], [170, 130], [95, 180], [35, 120]], dtype=np.int32)
    cv2.fillPoly(image, [points], (25, 25, 25))
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Failed to write image to {path}")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    board_path = RAW_DIR / "board.jpg"
    gap_path = RAW_DIR / "gap.jpg"
    piece_path = RAW_DIR / "piece.jpg"
    manifest_path = MANIFEST_DIR / "smoke-manifest.json"

    write_image(board_path, make_board_image())
    write_image(gap_path, make_gap_image())
    write_image(piece_path, make_piece_image())

    manifest = {
        "session_id": "session-smoke",
        "board_image": "../raw/smoke/board.jpg",
        "board_corners": [
            {"x": 0.10, "y": 0.10},
            {"x": 0.90, "y": 0.10},
            {"x": 0.90, "y": 0.90},
            {"x": 0.10, "y": 0.90},
        ],
        "queries": [
            {
                "query_id": "query-smoke-001",
                "gap_tap": {"x": 0.50, "y": 0.50},
                "manual_correction": {
                    "rough_polygon": [
                        {"x": 0.45, "y": 0.45},
                        {"x": 0.55, "y": 0.45},
                        {"x": 0.55, "y": 0.55},
                        {"x": 0.45, "y": 0.55},
                    ]
                },
                "truth_candidate_id": "proposal-006",
                "candidate_scans": [
                    {
                        "candidate_id": "proposal-006",
                        "image": "../raw/smoke/piece.jpg",
                    }
                ],
                "gap_image": "../raw/smoke/gap.jpg",
                "notes": "Synthetic smoke fixture for local validation and evaluation.",
            }
        ],
    }

    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
