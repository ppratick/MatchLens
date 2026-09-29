from __future__ import annotations

import cv2
import numpy as np

from .domain import Calibration


def calibrate(payload: dict) -> dict:
    item = Calibration.model_validate(payload).model_dump()
    image, field = np.array(item["image"], dtype=float), np.array(item["field"], dtype=float)
    if (
        image.shape != field.shape
        or image.shape[1] != 2
        or not np.isfinite(image).all()
        or not np.isfinite(field).all()
    ):
        raise ValueError("Provide paired x/y coordinates")
    if (image < 0).any() or (image > 1).any() or (field < 0).any() or (field > 1).any():
        raise ValueError("Calibration coordinates must be normalized to 0–1")
    if item["end"] <= item["start"]:
        raise ValueError("Invalid calibration interval")
    for points in (image, field):
        if cv2.contourArea(cv2.convexHull(points.astype(np.float32))) < 0.002:
            raise ValueError("Calibration points must cover an area, not a line")
    matrix, mask = cv2.findHomography(image, field, cv2.RANSAC, 0.025)
    if matrix is None or not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e7:
        raise ValueError("Unstable calibration; use more widely spread points")
    predicted = cv2.perspectiveTransform(image.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    item.update(
        matrix=matrix.tolist(),
        fit_error=float(np.median(np.linalg.norm(predicted - field, axis=1))),
        inliers=int(mask.sum()),
        reliability="unvalidated",
        field_polygon=cv2.convexHull(field.astype(np.float32)).reshape(-1, 2).tolist(),
    )
    return item


def project(calibration: dict, point: list[float]) -> list[float] | None:
    image_polygon = cv2.convexHull(np.array(calibration["image"], dtype=np.float32))
    if cv2.pointPolygonTest(image_polygon, (float(point[0]), float(point[1])), False) < 0:
        return None
    vector = np.array(calibration["matrix"]) @ [point[0], point[1], 1]
    if abs(vector[2]) < 1e-9:
        return None
    x, y = vector[:2] / vector[2]
    if not np.isfinite([x, y]).all() or not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    return [float(x), float(y)]


def apply_review(frame: dict, review: dict) -> dict:
    import copy

    result = copy.deepcopy(frame)
    t, source = frame["time"], frame["source_id"]
    result["excluded"] = any(
        x["start"] <= t < x["end"] and x.get("source_id", source) == source for x in review["exclusions"]
    )
    calibration = next(
        (
            c
            for c in reversed(review["calibrations"])
            if c["source_id"] == source and c["start"] <= t < c["end"]
        ),
        None,
    )
    if calibration and frame.get("last_cut", -1) > calibration["start"]:
        calibration = None
    for track in result["tracks"]:
        track["player"] = ""
        track["team"] = "unknown"
        track["role"] = "ball" if track["kind"] == "ball" else "player"
        track["display_id"] = track["id"]
        for label in review["labels"]:
            if label["track_id"] == track["id"] and label["start"] <= t < label["end"]:
                track.update({k: label[k] for k in ("team", "player", "role")})
                track["display_id"] = label.get("alias") or track["id"]
        x1, y1, x2, y2 = track["box"]
        point = [(x1 + x2) / 2, y2]
        for edit in review["points"]:
            if edit["track_id"] == track["id"] and abs(edit["time"] - t) < 0.001:
                point = edit["point"]
        track["ground_point"] = point
        track["field"] = project(calibration, point) if calibration and track["kind"] != "ball" else None
    result["calibrated"] = calibration is not None
    return result
