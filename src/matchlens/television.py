"""Manual television rectification, with conservative outside-screen movement checks."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import Field, model_validator

from .domain import StrictModel, uid


class TelevisionCalibration(StrictModel):
    corners: list[list[float]] = Field(min_length=4, max_length=4)
    start: float = Field(default=0, ge=0)
    width: int = Field(default=1280, ge=320, le=1920)
    height: int = Field(default=720, ge=180, le=1080)

    @model_validator(mode="after")
    def valid(self):
        points = np.array(self.corners, np.float32)
        if (
            points.shape != (4, 2)
            or not np.isfinite(points).all()
            or (points < 0).any()
            or (points > 1).any()
        ):
            raise ValueError("Television corners must be four normalized x/y points")
        if not cv2.isContourConvex(points) or cv2.contourArea(points, oriented=True) < 0.02:
            raise ValueError(
                "Mark a convex television clockwise: top-left, top-right, bottom-right, bottom-left"
            )
        return self


def warp_matrix(calibration: dict, shape):
    h, w = shape[:2]
    corners = np.array(calibration["corners"], np.float32) * [w - 1, h - 1]
    width, height = calibration["width"], calibration["height"]
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    return cv2.getPerspectiveTransform(corners.astype(np.float32), target)


def rectify(image, calibration: dict):
    matrix = warp_matrix(calibration, image.shape)
    return cv2.warpPerspective(image, matrix, (calibration["width"], calibration["height"]))


def original_box(box, calibration: dict, shape):
    """Return detection to original coordinates, keeping UI/review/export geometry consistent."""
    x1, y1, x2, y2 = box
    points = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], np.float32)
    points *= [calibration["width"] - 1, calibration["height"] - 1]
    inverse = np.linalg.inv(warp_matrix(calibration, shape))
    mapped = cv2.perspectiveTransform(points.reshape(-1, 1, 2), inverse).reshape(-1, 2)
    h, w = shape[:2]
    mapped /= [w - 1, h - 1]
    return np.clip([*mapped.min(axis=0), *mapped.max(axis=0)], 0, 1).tolist()


class MovementGuard:
    """Match static walls/TV border, never the changing soccer picture inside the TV."""

    def __init__(self, reference, calibration):
        self.orb = cv2.ORB_create(nfeatures=800)
        self.reference = cv2.resize(reference, (640, 360))
        polygon = (np.array(calibration["corners"]) * [639, 359]).astype(np.int32)
        mask = np.full((360, 640), 255, np.uint8)
        cv2.fillConvexPoly(mask, polygon, 0)
        self.mask = cv2.erode(mask, np.ones((7, 7), np.uint8))
        self.points, self.descriptors = self.orb.detectAndCompute(self.reference, self.mask)
        self.invalid = False

    def check(self, image):
        if self.invalid:
            return "moved"
        if self.descriptors is None or len(self.points) < 12:
            return "unavailable"
        current = cv2.resize(image, (640, 360))
        points, descriptors = self.orb.detectAndCompute(current, self.mask)
        if descriptors is None or len(points) < 8:
            return "obscured"
        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(self.descriptors, descriptors, k=2)
        good = [a for pair in matches if len(pair) == 2 for a, b in [pair] if a.distance < 0.72 * b.distance]
        if len(good) < 8:
            return "obscured"
        src = np.float32([self.points[m.queryIdx].pt for m in good])
        dst = np.float32([points[m.trainIdx].pt for m in good])
        matrix, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 3)
        if matrix is None or inliers.sum() < 8:
            return "obscured"
        probes = np.float32([[100, 100], [540, 100], [540, 260], [100, 260]]).reshape(-1, 1, 2)
        drift = np.linalg.norm(cv2.perspectiveTransform(probes, matrix) - probes, axis=2)
        if float(np.median(drift)) > 8:
            self.invalid = True
            return "moved"
        return "stable"


def decode_reference_image(data: str):
    import base64

    if not data.startswith("data:image/") or len(data) > 8 * 1024 * 1024:
        raise ValueError("Provide a local reference frame under 8 MiB")
    try:
        raw = base64.b64decode(data.split(",", 1)[1], validate=True)
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (ValueError, IndexError) as exc:
        raise ValueError("Invalid reference image") from exc
    if image is None or image.size > 40_000_000:
        raise ValueError("Invalid or oversized reference image")
    return image, raw


def prepare_setup(store, match_id: str, source_id: str, body: dict):
    from .media import sha256

    source = store.source(match_id, source_id)
    calibration = TelevisionCalibration.model_validate(body["calibration"]).model_dump()
    if calibration["start"] > source.get("duration", 0) + source.get("offset", 0):
        raise ValueError("Calibration starts outside received video")
    image, _ = decode_reference_image(str(body.get("reference_image", "")))
    path = store.path(match_id, f"thumbnails/tv-{uid()}.jpg")
    cv2.imwrite(str(path), cv2.resize(image, (640, 360)))
    calibration.update(
        reference=str(path.relative_to(store.settings.match_dir(match_id))), reference_sha256=sha256(path)
    )
    return calibration


def save_setup(store, match_id: str, source_id: str, body: dict):
    calibration = prepare_setup(store, match_id, source_id, body)

    def transform(state):
        state.setdefault("television", {})[source_id] = calibration
        return state

    result = store.edit(match_id, int(body["revision"]), "television_setup", transform)
    return {
        "revision": result,
        "calibration": calibration,
        "instructions": "Start a new analysis run to apply this setup. Original recording stays unchanged.",
    }
