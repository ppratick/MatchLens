from matchlens.evaluation import class_metrics


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
