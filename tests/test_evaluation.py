import base64
import json

import cv2
import numpy as np
import pytest

from matchlens.domain import Detection
from matchlens.evaluation import benchmark_video, class_metrics
from matchlens.media import run_media, sha256


def test_small_ball_size_bin_uses_ground_truth_not_prediction_size():
    truth = [{"time": 0, "objects": [{"id": "ball", "kind": "ball", "box": [0.1, 0.1, 0.12, 0.12]}]}]
    predicted = [
        {"time": 0, "tracks": [], "detections": [{"kind": "ball", "box": [0.098, 0.098, 0.122, 0.122]}]}
    ]
    result = class_metrics(predicted, truth, "ball", 0.1, max_area=0.0005)
    assert result["tp"] == 1 and result["recall"] == 1


def test_large_ball_does_not_count_as_small_ball_false_positive():
    box = [0.1, 0.1, 0.2, 0.2]
    truth = [{"time": 0, "objects": [{"id": "ball", "kind": "ball", "box": box}]}]
    predicted = [{"time": 0, "tracks": [], "detections": [{"kind": "ball", "box": box}]}]
    result = class_metrics(predicted, truth, "ball", 0.1, max_area=0.0005)
    assert result["tp"] == result["fp"] == result["fn"] == 0
    assert result["precision"] is None


@pytest.fixture
def benchmark_fixture(store, tmp_path):
    video = tmp_path / "fixture.mp4"
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=2",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        timeout=30,
    )
    return video


def test_benchmark_rectifies_tv_without_changing_label_coordinates(
    store, benchmark_fixture, tmp_path, monkeypatch
):
    class FixtureDetector:
        name = "geometry-test-double"

        def detect(self, image):
            assert image.shape == (180, 320, 3)
            return [Detection(kind="person", box=[0.25, 0.2, 0.5, 0.4], score=0.9)]

    monkeypatch.setattr("matchlens.evaluation.detector_for", lambda *args: FixtureDetector())
    _, encoded = cv2.imencode(".jpg", np.zeros((360, 640, 3), dtype=np.uint8))
    checksum = sha256(benchmark_fixture)
    labels = {
        "source_sha256": checksum,
        "source_profile": "phone_tv",
        "revision": 7,
        "television": {
            "calibration": {
                "corners": [[0.2, 0.1], [0.6, 0.1], [0.6, 0.9], [0.2, 0.9]],
                "width": 320,
                "height": 180,
            },
            "reference_image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode(),
        },
        "intervals": [
            {"kind": "camera_cut", "start": 0.5, "end": 0.501},
            {"kind": "replay", "start": 1, "end": 1.5},
        ],
        "frames": [
            {"time": t, "objects": [{"id": "p1", "box": [0.3, 0.26, 0.4, 0.42]}]} for t in [0, 0.5, 1, 1.5]
        ],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(labels))
    result = benchmark_video(store.settings, benchmark_fixture, 2, "hog", path, profile="phone_tv")
    assert result["preprocessing"]["mode"] == "television_rectified"
    assert result["annotation_sha256"] == sha256(path) and result["annotation_revision"] == 7
    assert result["processed_frames"] == 4 and result["inference_frames"] == 3
    assert result["shot_resets"] >= 1 and result["reviewed_withheld_frames"] == 1
    assert result["television_movement_samples"] == {"unavailable": 4}
    assert result["accuracy"]["players"]["tp"] == 3
    assert result["accuracy"]["review_excluded_labeled_frames"] == 1
    assert sha256(benchmark_fixture) == checksum


@pytest.mark.parametrize("field,value", [("source_sha256", "0" * 64), ("source_profile", "screen")])
def test_benchmark_refuses_mismatched_ground_truth(store, benchmark_fixture, tmp_path, field, value):
    labels = {"source_sha256": sha256(benchmark_fixture), "source_profile": "broadcast", "frames": []}
    labels[field] = value
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(labels))
    with pytest.raises(ValueError, match="checksum|profile"):
        benchmark_video(store.settings, benchmark_fixture, 2, "hog", path, profile="broadcast")
