import cv2
import numpy as np
import pytest

from matchlens.television import MovementGuard, TelevisionCalibration, original_box, rectify


def calibration():
    return TelevisionCalibration(
        corners=[[0.2, 0.2], [0.8, 0.25], [0.85, 0.8], [0.15, 0.8]], width=640, height=360
    ).model_dump()


def test_rectification_and_inverse_coordinates():
    c = calibration()
    image = np.zeros((540, 960, 3), np.uint8)
    cv2.fillConvexPoly(image, (np.array(c["corners"]) * [959, 539]).astype(np.int32), (30, 150, 80))
    warped = rectify(image, c)
    assert warped.shape == (360, 640, 3)
    assert np.median(warped[:, :, 1]) == pytest.approx(150, abs=3)
    box = original_box([0, 0, 1, 1], c, image.shape)
    assert box == pytest.approx([0.15, 0.2, 0.85, 0.8], abs=0.001)
    assert not image[0, 0].any()


@pytest.mark.parametrize(
    "corners",
    [
        [[0, 0], [1, 1], [1, 0], [0, 1]],
        [[0, 0], [0.1, 0], [0.2, 0], [0.3, 0]],
        [[0, 0], [2, 0], [1, 1], [0, 1]],
    ],
)
def test_degenerate_and_unordered_screen_rejected(corners):
    with pytest.raises(ValueError):
        TelevisionCalibration(corners=corners)


def test_movement_guard_ignores_soccer_picture_and_latches_camera_motion():
    rng = np.random.default_rng(17)
    reference = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    c = TelevisionCalibration(
        corners=[[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]], width=640, height=360
    ).model_dump()
    reference[90:270, 160:480] = [30, 150, 80]
    guard = MovementGuard(reference, c)
    changed = reference.copy()
    changed[90:270, 160:480] = [220, 40, 90]
    assert guard.check(changed) == "stable"
    shifted = cv2.warpAffine(reference, np.float32([[1, 0, 20], [0, 1, 10]]), (640, 360))
    assert guard.check(shifted) == "moved"
    assert guard.check(reference) == "moved"
    assert MovementGuard(np.zeros_like(reference), c).check(reference) == "unavailable"
