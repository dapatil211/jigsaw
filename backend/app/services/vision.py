from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.models.schemas import (
    BoardCapturePayload,
    BoardCaptureRecord,
    BoundingBox,
    GapQueryPayload,
    GapQueryRecord,
    MatchCandidate,
    PieceProposal,
    PieceScanPayload,
    Point,
    QueryTarget,
)


DESCRIPTOR_LENGTH = 64
ALIGNMENT_POINT_COUNT = 64
MIN_COMPONENT_AREA_RATIO = 0.0002
CLUSTER_AREA_RATIO = 0.02
LOW_CONFIDENCE_THRESHOLD = 0.55
HIGH_CONFIDENCE_THRESHOLD = 0.82


@dataclass
class BoardAnalysis:
    rectified_image_bytes: bytes | None
    rectified_width: int | None
    rectified_height: int | None
    piece_proposals: list[PieceProposal]


@dataclass
class GapAnalysis:
    target: QueryTarget | None
    candidates: list[MatchCandidate]
    confidence: str
    needs_manual_correction: bool
    message: str | None


@dataclass
class PieceScanAnalysis:
    updated_query: GapQueryRecord | None


def read_image_dimensions(content: bytes) -> tuple[int | None, int | None]:
    image = _decode_image(content)
    if image is None:
        return None, None
    height, width = image.shape[:2]
    return width, height


def analyze_board_capture(image_path: Path, payload: BoardCapturePayload) -> BoardAnalysis:
    image = _read_image(image_path)
    ordered_corners = None
    rectified = None
    if payload.kind == "board" and payload.corners:
        corners = _normalized_points_to_pixels(payload.corners, image.shape[1], image.shape[0])
        ordered_corners = _order_quad(corners)
        rectified = _rectify_board(image, ordered_corners)
    rectified_bytes = None
    rectified_width = None
    rectified_height = None
    if rectified is not None:
        ok, encoded = cv2.imencode(".png", rectified)
        if ok:
            rectified_bytes = encoded.tobytes()
            rectified_height, rectified_width = rectified.shape[:2]
    piece_proposals = _propose_loose_regions(image, ordered_corners)
    return BoardAnalysis(
        rectified_image_bytes=rectified_bytes,
        rectified_width=rectified_width,
        rectified_height=rectified_height,
        piece_proposals=piece_proposals,
    )


def analyze_gap_query(
    board_image_path: Path,
    gap_image_path: Path | None,
    board_capture: BoardCaptureRecord,
    candidate_captures: list[BoardCaptureRecord],
    payload: GapQueryPayload,
) -> GapAnalysis:
    board_image = _read_image(board_image_path)
    gap_image = _read_image(gap_image_path) if gap_image_path else None
    target = _extract_gap_target(board_image, gap_image, payload)
    if target is None:
        return GapAnalysis(
            target=None,
            candidates=[],
            confidence="failed_extraction",
            needs_manual_correction=True,
            message="Gap extraction failed. Add a correction polygon or extra tap and retry.",
        )

    candidate_proposals = [
        proposal for capture in candidate_captures for proposal in capture.piece_proposals
    ]
    candidates = _score_candidates(candidate_proposals, target, payload)
    if not candidates:
        return GapAnalysis(
            target=target,
            candidates=[],
            confidence="failed_extraction",
            needs_manual_correction=False,
            message="No loose-piece proposals were detected. Capture a fresher board image or scan candidates directly.",
        )

    top_score = candidates[0].score
    confidence = "needs_piece_scan"
    if top_score >= HIGH_CONFIDENCE_THRESHOLD:
        confidence = "high_confidence"
    elif top_score >= LOW_CONFIDENCE_THRESHOLD:
        confidence = "medium_confidence"

    return GapAnalysis(
        target=target,
        candidates=candidates[:5],
        confidence=confidence,
        needs_manual_correction=False,
        message="Baseline contour ranking complete.",
    )


def analyze_piece_scan(
    piece_image_path: Path, query: GapQueryRecord, payload: PieceScanPayload
) -> PieceScanAnalysis:
    if query.target is None:
        return PieceScanAnalysis(updated_query=query)

    piece_image = _read_image(piece_image_path)
    contour = _largest_contour(piece_image)
    if contour is None:
        return PieceScanAnalysis(updated_query=query)

    scan_features = _extract_contour_features(contour, piece_image.shape[1], piece_image.shape[0])
    updated_candidates: list[MatchCandidate] = []
    for candidate in query.candidates:
        if payload.candidate_id and candidate.candidate_id != payload.candidate_id:
            updated_candidates.append(candidate)
            continue
        target_score = _target_to_scan_similarity(query.target, scan_features)
        candidate_score = _scan_to_candidate_similarity(candidate, scan_features)
        blended = min(
            1.0,
            max(
                candidate.score,
                0.2 * candidate.score + 0.45 * target_score + 0.35 * candidate_score,
            ),
        )
        reasons = list(dict.fromkeys(candidate.reasons + ["piece_scan_verified"]))
        confidence = candidate.confidence
        if blended >= HIGH_CONFIDENCE_THRESHOLD:
            confidence = "high_confidence"
        elif blended >= LOW_CONFIDENCE_THRESHOLD:
            confidence = "medium_confidence"
        else:
            confidence = "needs_piece_scan"
        updated_candidates.append(
            candidate.model_copy(
                update={
                    "score": blended,
                    "confidence": confidence,
                    "reasons": reasons,
                    "needs_piece_scan": False if blended >= LOW_CONFIDENCE_THRESHOLD else True,
                }
            )
        )
    updated_candidates.sort(key=lambda item: item.score, reverse=True)
    updated_query = query.model_copy(
        update={
            "candidates": updated_candidates,
            "confidence": updated_candidates[0].confidence if updated_candidates else query.confidence,
            "message": "Close-up verification applied.",
        }
    )
    return PieceScanAnalysis(updated_query=updated_query)


def _decode_image(content: bytes) -> np.ndarray | None:
    array = np.frombuffer(content, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _read_image(path: Path | None) -> np.ndarray:
    if path is None:
        raise ValueError("Image path is required.")
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Failed to read image: {path}")
    return image


def _normalized_points_to_pixels(points, width: int, height: int) -> np.ndarray:
    return np.array([[point.x * width, point.y * height] for point in points], dtype=np.float32)


def _order_quad(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def _rectify_board(image: np.ndarray, corners: np.ndarray) -> np.ndarray | None:
    tl, tr, br, bl = corners
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = int(max(width_a, width_b))
    max_height = int(max(height_a, height_b))
    if max_width < 10 or max_height < 10:
        return None
    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(image, transform, (max_width, max_height))


def _preprocess_for_edges(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    normalized = clahe.apply(gray)
    return cv2.GaussianBlur(normalized, (5, 5), 0)


def _propose_loose_regions(image: np.ndarray, board_corners: np.ndarray | None) -> list[PieceProposal]:
    blurred = _preprocess_for_edges(image)
    edges = cv2.Canny(blurred, 45, 120)
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    board_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    if board_corners is not None:
        cv2.fillConvexPoly(board_mask, board_corners.astype(np.int32), 255)
    image_area = float(image.shape[0] * image.shape[1])
    proposals: list[PieceProposal] = []
    counter = 1
    for contour in contours:
        area = cv2.contourArea(contour)
        area_ratio = area / image_area
        if area_ratio < MIN_COMPONENT_AREA_RATIO:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        if board_corners is not None and 0 <= cx < board_mask.shape[1] and 0 <= cy < board_mask.shape[0] and board_mask[cy, cx] > 0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        hull = cv2.convexHull(contour)
        hull_area = max(cv2.contourArea(hull), 1.0)
        solidity = min(1.0, area / hull_area)
        extent = min(1.0, area / max(w * h, 1.0))
        is_cluster = area_ratio > CLUSTER_AREA_RATIO or solidity < 0.58
        confidence = float(np.clip((solidity * 0.8) + (0.15 if not is_cluster else -0.1), 0.05, 0.95))
        features = _extract_contour_features(contour, image.shape[1], image.shape[0])
        proposals.append(
            PieceProposal(
                candidate_id=f"proposal-{counter:03d}",
                label=f"Proposal {counter:03d}",
                source_board_capture_id=None,
                source_board_capture_version=None,
                bbox=BoundingBox(
                    x=x / image.shape[1],
                    y=y / image.shape[0],
                    width=w / image.shape[1],
                    height=h / image.shape[0],
                ),
                area_ratio=area_ratio,
                confidence=confidence,
                is_cluster=is_cluster,
                needs_closeup=is_cluster or confidence < 0.45,
                descriptor=features["descriptor"],
                contour_points=features["contour_points"],
                hu_moments=features["hu_moments"],
                aspect_ratio=features["aspect_ratio"],
                extent=extent,
                solidity=solidity,
                complexity=features["complexity"],
            )
        )
        counter += 1
    proposals.sort(key=lambda item: (item.needs_closeup, -item.confidence, item.is_cluster))
    return proposals


def _extract_gap_target(
    board_image: np.ndarray, gap_image: np.ndarray | None, payload: GapQueryPayload
) -> QueryTarget | None:
    source = gap_image if gap_image is not None else board_image
    height, width = source.shape[:2]
    tap_x = int(payload.tap.x * width)
    tap_y = int(payload.tap.y * height)

    if payload.manual_correction and payload.manual_correction.rough_polygon:
        polygon = _normalized_points_to_pixels(payload.manual_correction.rough_polygon, width, height)
        contour = polygon.reshape((-1, 1, 2)).astype(np.int32)
        x, y, w, h = cv2.boundingRect(contour)
        bbox = BoundingBox(x=x / width, y=y / height, width=w / width, height=h / height)
        features = _extract_contour_features(contour, width, height)
        return QueryTarget(
            source_artifact_id=None,
            bbox=bbox,
            descriptor=features["descriptor"],
            contour_points=features["contour_points"],
            hu_moments=features["hu_moments"],
            aspect_ratio=features["aspect_ratio"],
            extent=features["extent"],
            solidity=features["solidity"],
            complexity=features["complexity"],
            extraction_confidence=0.82,
            used_manual_correction=True,
        )

    crop_radius = int(min(width, height) * 0.18)
    if payload.manual_correction and payload.manual_correction.extra_tap is not None:
        tap_x = int(payload.manual_correction.extra_tap.x * width)
        tap_y = int(payload.manual_correction.extra_tap.y * height)
    x0 = max(tap_x - crop_radius, 0)
    y0 = max(tap_y - crop_radius, 0)
    x1 = min(tap_x + crop_radius, width)
    y1 = min(tap_y + crop_radius, height)
    crop = source[y0:y1, x0:x1]
    contour = _best_gap_contour(crop)
    if contour is None:
        return None
    bx, by, bw, bh = cv2.boundingRect(contour)
    features = _extract_contour_features(contour, crop.shape[1], crop.shape[0])
    bbox = BoundingBox(
        x=(x0 + bx) / width,
        y=(y0 + by) / height,
        width=bw / width,
        height=bh / height,
    )
    return QueryTarget(
        source_artifact_id=None,
        bbox=bbox,
        descriptor=features["descriptor"],
        contour_points=features["contour_points"],
        hu_moments=features["hu_moments"],
        aspect_ratio=features["aspect_ratio"],
        extent=features["extent"],
        solidity=features["solidity"],
        complexity=features["complexity"],
        extraction_confidence=0.44 if gap_image is None else 0.63,
        used_manual_correction=False,
    )


def _largest_contour(image: np.ndarray) -> np.ndarray | None:
    blurred = _preprocess_for_edges(image)
    edges = cv2.Canny(blurred, 45, 120)
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) > 24.0]
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _best_gap_contour(image: np.ndarray) -> np.ndarray | None:
    blurred = _preprocess_for_edges(image)
    edges = cv2.Canny(blurred, 45, 120)
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) > 24.0]
    if not contours:
        return None

    height, width = image.shape[:2]
    center = np.array([width / 2.0, height / 2.0], dtype=np.float32)
    best_score = -1.0
    best_contour = None
    image_area = float(width * height)
    for contour in contours:
        area = cv2.contourArea(contour)
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        centroid = np.array(
            [moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]],
            dtype=np.float32,
        )
        center_distance = np.linalg.norm(centroid - center) / max(np.linalg.norm(center), 1.0)
        area_score = min(1.0, area / max(image_area * 0.01, 1.0))
        score = area_score * 0.65 + (1.0 - min(center_distance, 1.0)) * 0.35
        if score > best_score:
            best_score = score
            best_contour = contour
    return best_contour


def _contour_signature(contour: np.ndarray) -> list[float]:
    contour = contour.reshape(-1, 2).astype(np.float32)
    if len(contour) < 3:
        return [0.0] * DESCRIPTOR_LENGTH
    centroid = contour.mean(axis=0)
    radii = np.linalg.norm(contour - centroid, axis=1)
    if np.allclose(radii.mean(), 0.0):
        return [0.0] * DESCRIPTOR_LENGTH
    radii = radii / radii.mean()
    base_x = np.linspace(0.0, 1.0, num=len(radii), endpoint=False)
    target_x = np.linspace(0.0, 1.0, num=DESCRIPTOR_LENGTH, endpoint=False)
    signature = np.interp(target_x, base_x, radii)
    return signature.astype(float).tolist()


def _extract_contour_features(
    contour: np.ndarray, image_width: int, image_height: int
) -> dict[str, float | list[float] | list]:
    x, y, width, height = cv2.boundingRect(contour)
    area = max(cv2.contourArea(contour), 1.0)
    perimeter = max(cv2.arcLength(contour, True), 1.0)
    hull = cv2.convexHull(contour)
    hull_area = max(cv2.contourArea(hull), 1.0)
    extent = min(1.0, area / max(width * height, 1.0))
    solidity = min(1.0, area / hull_area)
    aspect_ratio = max(width / max(height, 1.0), 1e-6)
    complexity = float((perimeter * perimeter) / (4.0 * np.pi * area))
    hu_moments = cv2.HuMoments(cv2.moments(contour)).flatten()
    hu_moments = [float(-np.sign(value) * np.log10(abs(value) + 1e-12)) for value in hu_moments]
    contour_points = _normalized_contour_points(contour)

    return {
        "descriptor": _contour_signature(contour),
        "contour_points": contour_points,
        "hu_moments": hu_moments,
        "aspect_ratio": float(aspect_ratio),
        "extent": float(extent),
        "solidity": float(solidity),
        "complexity": float(complexity),
        "bbox_x": x / max(image_width, 1),
        "bbox_y": y / max(image_height, 1),
    }


def _normalized_contour_points(contour: np.ndarray) -> list:
    points = contour.reshape(-1, 2).astype(np.float32)
    if len(points) < 2:
        return []

    points = _resample_closed_contour(points, ALIGNMENT_POINT_COUNT)
    min_xy = points.min(axis=0)
    max_xy = points.max(axis=0)
    scale = np.maximum(max_xy - min_xy, 1e-6)
    normalized = (points - min_xy) / scale

    return [Point(x=float(point[0]), y=float(point[1])) for point in normalized]


def _resample_closed_contour(points: np.ndarray, sample_count: int) -> np.ndarray:
    if len(points) == 0:
        return np.zeros((sample_count, 2), dtype=np.float32)
    closed = np.vstack([points, points[0]])
    segment_lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total = cumulative[-1]
    if total <= 1e-6:
        return np.repeat(points[:1], sample_count, axis=0)
    sample_positions = np.linspace(0.0, total, num=sample_count, endpoint=False)
    x = np.interp(sample_positions, cumulative, closed[:, 0])
    y = np.interp(sample_positions, cumulative, closed[:, 1])
    return np.column_stack([x, y]).astype(np.float32)


def _signature_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    left_arr = np.asarray(left, dtype=np.float32)
    right_arr = np.asarray(right, dtype=np.float32)
    best = 0.0
    for shift in range(len(right_arr)):
        shifted = np.roll(right_arr, shift)
        mse = float(np.mean((left_arr - shifted) ** 2))
        best = max(best, 1.0 / (1.0 + mse * 8.0))
    return float(np.clip(best, 0.0, 1.0))


def _contour_alignment_similarity(left_points: list, right_points: list) -> float:
    if not left_points or not right_points:
        return 0.0

    left = np.array([[point.x, point.y] for point in left_points], dtype=np.float32)
    right = np.array([[point.x, point.y] for point in right_points], dtype=np.float32)
    if len(left) != len(right):
        sample_count = max(len(left), len(right), ALIGNMENT_POINT_COUNT)
        left = _resample_closed_contour(left, sample_count)
        right = _resample_closed_contour(right, sample_count)

    left = _normalize_alignment_points(left)
    right = _normalize_alignment_points(right)

    best_distance = float("inf")
    for variant in (right, right[::-1]):
        for shift in range(len(variant)):
            shifted = np.roll(variant, shift, axis=0)
            distance = float(np.mean(np.linalg.norm(left - shifted, axis=1)))
            if distance < best_distance:
                best_distance = distance
    return float(1.0 / (1.0 + best_distance * 3.5))


def _normalize_alignment_points(points: np.ndarray) -> np.ndarray:
    centered = points - points.mean(axis=0, keepdims=True)
    scale = max(float(np.linalg.norm(centered, axis=1).mean()), 1e-6)
    return centered / scale


def _hu_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    left_arr = np.asarray(left, dtype=np.float32)
    right_arr = np.asarray(right, dtype=np.float32)
    distance = float(np.mean(np.abs(left_arr - right_arr)))
    return float(1.0 / (1.0 + distance))


def _ratio_similarity(left: float, right: float) -> float:
    left = max(left, 1e-6)
    right = max(right, 1e-6)
    return float(np.exp(-abs(np.log(left / right))))


def _target_to_scan_similarity(target: QueryTarget, scan_features: dict) -> float:
    return _blend_shape_scores(
        descriptor_score=_signature_similarity(target.descriptor, scan_features["descriptor"]),
        alignment_score=_contour_alignment_similarity(target.contour_points, scan_features["contour_points"]),
        hu_score=_hu_similarity(target.hu_moments, scan_features["hu_moments"]),
        aspect_score=_ratio_similarity(target.aspect_ratio, float(scan_features["aspect_ratio"])),
        extent_score=1.0 - min(1.0, abs(target.extent - float(scan_features["extent"]))),
        solidity_score=1.0 - min(1.0, abs(target.solidity - float(scan_features["solidity"]))),
        complexity_score=_ratio_similarity(target.complexity, float(scan_features["complexity"])),
    )


def _scan_to_candidate_similarity(candidate: MatchCandidate, scan_features: dict) -> float:
    contour_points = candidate.contour_points
    hu_moments = candidate.hu_moments
    aspect_ratio = candidate.aspect_ratio or float(scan_features["aspect_ratio"])
    extent = candidate.extent if candidate.extent is not None else float(scan_features["extent"])
    solidity = candidate.solidity if candidate.solidity is not None else float(scan_features["solidity"])
    complexity = candidate.complexity if candidate.complexity is not None else float(scan_features["complexity"])
    descriptor = candidate.descriptor
    return _blend_shape_scores(
        descriptor_score=_signature_similarity(descriptor, scan_features["descriptor"]) if descriptor else 0.0,
        alignment_score=_contour_alignment_similarity(contour_points, scan_features["contour_points"]) if contour_points else 0.0,
        hu_score=_hu_similarity(hu_moments, scan_features["hu_moments"]) if hu_moments else 0.0,
        aspect_score=_ratio_similarity(aspect_ratio, float(scan_features["aspect_ratio"])),
        extent_score=1.0 - min(1.0, abs(extent - float(scan_features["extent"]))),
        solidity_score=1.0 - min(1.0, abs(solidity - float(scan_features["solidity"]))),
        complexity_score=_ratio_similarity(complexity, float(scan_features["complexity"])),
    )


def _score_candidates(
    proposals: list[PieceProposal], target: QueryTarget, payload: GapQueryPayload
) -> list[MatchCandidate]:
    matches: list[MatchCandidate] = []
    for proposal in proposals:
        descriptor_score = _signature_similarity(target.descriptor, proposal.descriptor)
        alignment_score = _contour_alignment_similarity(target.contour_points, proposal.contour_points)
        hu_score = _hu_similarity(target.hu_moments, proposal.hu_moments)
        aspect_score = _ratio_similarity(target.aspect_ratio, proposal.aspect_ratio)
        extent_score = 1.0 - min(1.0, abs(target.extent - proposal.extent))
        solidity_score = 1.0 - min(1.0, abs(target.solidity - proposal.solidity))
        complexity_score = _ratio_similarity(target.complexity, proposal.complexity)
        score = _blend_shape_scores(
            descriptor_score=descriptor_score,
            alignment_score=alignment_score,
            hu_score=hu_score,
            aspect_score=aspect_score,
            extent_score=extent_score,
            solidity_score=solidity_score,
            complexity_score=complexity_score,
        )
        score *= 0.6 + 0.4 * proposal.confidence
        score *= 0.65 + 0.35 * target.extraction_confidence
        reasons = ["shape_match"]
        needs_piece_scan = proposal.needs_closeup or proposal.is_cluster
        confidence = "medium_confidence"
        if proposal.is_cluster:
            reasons.extend(["cluster_uncertain", "requires_piece_scan"])
            needs_piece_scan = True
            confidence = "needs_piece_scan"
            score *= 0.55
        if proposal.confidence < 0.45:
            reasons.append("low_segmentation_confidence")
            needs_piece_scan = True
            confidence = "needs_piece_scan"
            score *= 0.8
        if target.used_manual_correction:
            reasons.append("manual_correction_used")
        if not payload.gap_closeup_expected:
            reasons.append("no_gap_closeup")
            score *= 0.95
        if score >= HIGH_CONFIDENCE_THRESHOLD and not needs_piece_scan:
            confidence = "high_confidence"
        elif score < LOW_CONFIDENCE_THRESHOLD or needs_piece_scan:
            confidence = "needs_piece_scan"
        matches.append(
            MatchCandidate(
                candidate_id=proposal.candidate_id,
                label=proposal.label,
                source_board_capture_id=proposal.source_board_capture_id,
                source_board_capture_version=proposal.source_board_capture_version,
                score=float(np.clip(score, 0.0, 1.0)),
                confidence=confidence,
                reasons=reasons,
                bbox=proposal.bbox,
                is_cluster=proposal.is_cluster,
                needs_piece_scan=needs_piece_scan,
                descriptor=proposal.descriptor,
                contour_points=proposal.contour_points,
                hu_moments=proposal.hu_moments,
                aspect_ratio=proposal.aspect_ratio,
                extent=proposal.extent,
                solidity=proposal.solidity,
                complexity=proposal.complexity,
            )
        )
    matches.sort(key=lambda item: item.score, reverse=True)
    return matches


def _blend_shape_scores(
    *,
    descriptor_score: float,
    alignment_score: float,
    hu_score: float,
    aspect_score: float,
    extent_score: float,
    solidity_score: float,
    complexity_score: float,
) -> float:
    return float(
        0.28 * descriptor_score
        + 0.28 * alignment_score
        + 0.14 * hu_score
        + 0.10 * aspect_score
        + 0.08 * extent_score
        + 0.05 * solidity_score
        + 0.07 * complexity_score
    )
