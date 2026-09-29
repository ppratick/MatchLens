import json

import pytest

from matchlens.domain import Correction, Detection, Event
from matchlens.evaluation import event_metrics, match_boxes
from matchlens.geometry import apply_review, calibrate, project
from matchlens.review import correct, snapshot
from matchlens.sports import Soccer, union_intervals
from matchlens.storage import EMPTY_REVIEW, encode
from matchlens.tracking import Tracker


def test_rules_fixture():
    events = [
        Event(kind=k, start=t, end=end, team=team).model_dump()
        for k, t, end, team in [
            ("pass", 2, None, "home"),
            ("pass", 4, None, "home"),
            ("turnover", 6, None, "away"),
            ("goal", 12, None, "away"),
            ("possession", 0, 6, "home"),
            ("possession", 6, 12, "away"),
        ]
    ]
    result = Soccer().summarize(events, 20, [{"start": 12, "end": 15}])
    assert result["score"] == {"home": 0, "away": 1}
    assert result["counts"]["home"]["pass"] == 2
    assert result["possession"]["seconds"] == {"home": 6, "away": 6, "unknown": 5, "excluded": 3}
    assert result["possession"]["percent"] == {"home": 35.3, "away": 35.3, "unknown": 29.4}


def test_contradictory_possession_is_unknown():
    events = [Event(kind="possession", start=0, end=10, team=t).model_dump() for t in ("home", "away")]
    result = Soccer().summarize(events, 20, [])
    assert result["possession"]["seconds"]["unknown"] == 20


def test_interval_union():
    assert union_intervals([(2, 5), (0, 3), (8, 9), (9, 11), (4, 4)]) == [[0, 5], [8, 11]]


def test_reject_undo_redo_and_branch(store, match):
    e = Event(kind="goal", start=12, team="away").model_dump()
    correct(store, match, Correction(revision=0, operation="event", payload=e))
    assert snapshot(store, match)["statistics"]["score"]["away"] == 1
    correct(store, match, Correction(revision=1, operation="event", payload={**e, "status": "rejected"}))
    assert snapshot(store, match)["statistics"]["score"]["away"] == 0
    store.undo(match, 2)
    assert snapshot(store, match)["statistics"]["score"]["away"] == 1
    store.undo(match, 3, redo=True)
    assert snapshot(store, match)["statistics"]["score"]["away"] == 0
    store.undo(match, 4)
    correct(store, match, Correction(revision=5, operation="event", payload={**e, "team": "home"}))
    with pytest.raises(ValueError, match="Nothing to redo"):
        store.undo(match, 6, redo=True)
    # A fresh Store must observe the same reviewed state.
    from matchlens.storage import Store

    assert snapshot(Store(store.settings), match)["statistics"]["score"]["home"] == 1


def test_stale_edits_and_invalid_intervals(store, match):
    e = Event(kind="goal", start=5).model_dump()
    correct(store, match, Correction(revision=0, operation="event", payload=e))
    with pytest.raises(ValueError, match="Review changed"):
        correct(store, match, Correction(revision=0, operation="event", payload=e))
    with pytest.raises(ValueError):
        Event(kind="possession", start=3, end=2)
    with pytest.raises(ValueError):
        correct(store, match, Correction(revision=1, operation="event", payload={**e, "start": 30}))


def calibration():
    return calibrate(
        {
            "source_id": "camera",
            "image": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            "field": [[0, 0], [1, 0], [1, 1], [0, 1]],
        }
    )


def test_calibration_and_visibility():
    c = calibration()
    assert project(c, [0.5, 0.5]) == pytest.approx([0.5, 0.5])
    assert project(c, [0.99, 0.5]) is None
    with pytest.raises(ValueError, match="area"):
        calibrate(
            {
                "source_id": "s",
                "image": [[0, 0], [0.2, 0], [0.4, 0], [0.6, 0]],
                "field": [[0, 0], [1, 0], [1, 1], [0, 1]],
            }
        )


def test_camera_cut_invalidates_mapping():
    state = json.loads(encode(EMPTY_REVIEW))
    state["calibrations"] = [calibration()]
    frame = {
        "time": 3,
        "source_id": "camera",
        "last_cut": 2,
        "tracks": [{"id": "p", "box": [0.4, 0.3, 0.6, 0.5], "kind": "person"}],
    }
    assert apply_review(frame, state)["tracks"][0]["field"] is None
    state["calibrations"][0]["start"] = 2.5
    assert apply_review(frame, state)["tracks"][0]["field"] == pytest.approx([0.5, 0.5])


def test_tracker_checkpoint_and_low_confidence():
    t = Tracker("run")
    a = t.update([Detection(box=[0.1, 0.1, 0.2, 0.4], score=0.9)], 0)
    state = json.loads(json.dumps(t.state))
    b = t.update([Detection(box=[0.11, 0.1, 0.21, 0.4], score=0.3)], 0.2)
    resumed = Tracker("run", state).update([Detection(box=[0.11, 0.1, 0.21, 0.4], score=0.3)], 0.2)
    assert a[0]["id"] == b[0]["id"] == resumed[0]["id"]
    assert b == resumed
    assert not Tracker("r").update([Detection(box=[0.1, 0.1, 0.2, 0.4], score=0.2)], 0)


def test_missing_observation_is_not_a_predicted_fact():
    tracker = Tracker("r")
    tracker.update([Detection(box=[0.1, 0.1, 0.2, 0.4], score=0.9)], 0)
    assert tracker.update([], 0.2) == []
    assert tracker.update([Detection(box=[0.1, 0.1, 0.2, 0.4], score=0.9)], 4)[0]["id"] == "r-2"


def test_event_evaluation_one_to_one():
    result = event_metrics(
        [{"kind": "goal", "start": 10}, {"kind": "goal", "start": 11}], [{"kind": "goal", "start": 10}], 2
    )
    assert result["goal"]["precision"] == 0.5
    assert result["goal"]["recall"] == 1


def test_spatial_matching_cannot_reuse_truth():
    boxes = [{"box": [0, 0, 1, 1]}, {"box": [0, 0, 1, 1]}]
    assert len(match_boxes(boxes, boxes[:1])) == 1


def test_delete_managed_data_and_path_guard(store, match, tmp_path):
    external = tmp_path / "external.mp4"
    external.write_bytes(b"original")
    store.path(match, "original/test.mp4").write_bytes(b"copy")
    with pytest.raises(ValueError):
        store.path(match, "../../external.mp4")
    store.delete(match)
    assert not store.settings.match_dir(match).exists()
    assert external.read_bytes() == b"original"
    assert store.list() == []


def test_csv_formula_strings_are_neutralized():
    from matchlens.exports import csv_safe

    assert csv_safe({"note": "=1+1", "player": "@name", "time": -2}) == {
        "note": "'=1+1",
        "player": "'@name",
        "time": -2,
    }
