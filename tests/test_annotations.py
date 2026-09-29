import copy

import pytest
from fastapi.testclient import TestClient

from matchlens.annotations import AnnotationBundle, export_annotations, import_annotations
from matchlens.api import create_app
from matchlens.domain import MatchCreate
from matchlens.geometry import apply_review
from matchlens.media import sha256
from matchlens.profiles import profile_id, profiles
from matchlens.storage import Store


def source_fixture(store):
    mid = store.create(MatchCreate(title="Annotation fixture", profile="broadcast"))["id"]
    original = store.path(mid, "original/fixture.bin")
    original.write_bytes(b"preserved annotation source")
    source = {
        "id": "source",
        "path": "original/fixture.bin",
        "duration": 10,
        "sha256": sha256(original),
        "profile": "broadcast",
        "offset": 0,
        "status": "ready",
    }
    store.put_source(mid, source)
    return mid, source


def test_profile_domains_are_explicit():
    rows = profiles()
    assert {r["id"] for r in rows} == {"broadcast", "screen", "phone_tv", "synthetic", "sideline"}
    assert next(r for r in rows if r["id"] == "sideline")["status"] == "Coming later"
    assert all(r["evaluation"]["sample_count"] == 0 for r in rows)
    assert profile_id({"kind": "phone"}, "broadcast") == "phone_tv"


def test_annotation_exchange_restart_undo_and_original_coordinates(store):
    mid, source = source_fixture(store)
    bundle = export_annotations(store, mid, source["id"])
    bundle["frames"] = [
        {
            "time": 1.2,
            "objects": [{"id": "player-7", "track_id": "run-7", "box": [0.1, 0.2, 0.3, 0.8], "team": "home"}],
        }
    ]
    bundle["intervals"] = [{"kind": "replay", "start": 2, "end": 4}]
    bundle["events"] = [{"kind": "goal", "start": 3, "team": "away"}]
    assert import_annotations(store, mid, source["id"], AnnotationBundle.model_validate(bundle), 0) == 1
    reopened = Store(store.settings)
    exported = export_annotations(reopened, mid, source["id"])
    assert exported["revision"] == 1
    assert exported["frames"][0]["objects"][0]["id"] == "player-7"
    frame = {"time": 1.2, "source_id": source["id"], "tracks": [], "last_cut": -1}
    reviewed = apply_review(frame, reopened.review(mid)[1])
    assert reviewed["tracks"][0]["box"] == [0.1, 0.2, 0.3, 0.8]
    assert reviewed["tracks"][0]["team"] == "home"
    assert reviewed["tracks"][0]["id"] == "run-7"
    assert apply_review({**frame, "time": 3}, reopened.review(mid)[1])["excluded"]
    reopened.undo(mid, 1)
    assert export_annotations(reopened, mid, source["id"])["frames"] == []
    reopened.undo(mid, 2, redo=True)
    assert len(export_annotations(reopened, mid, source["id"])["frames"]) == 1
    assert sha256(store.path(mid, source["path"])) == bundle["source_sha256"]


@pytest.mark.parametrize(
    "change,error",
    [
        ({"source_sha256": "0" * 64}, "checksum"),
        ({"source_profile": "phone_tv"}, "profile"),
        ({"source_offset": 2}, "alignment"),
        ({"frames": [{"time": 50}]}, "outside"),
    ],
)
def test_mismatched_labels_are_rejected(store, change, error):
    mid, source = source_fixture(store)
    bundle = export_annotations(store, mid, source["id"])
    bundle.update(change)
    with pytest.raises(ValueError, match=error):
        import_annotations(store, mid, source["id"], AnnotationBundle.model_validate(bundle), 0)
    assert store.review(mid)[0] == 0


def test_schema_and_http_revision_conflicts(store):
    mid, source = source_fixture(store)
    with TestClient(create_app(store.settings, testing=True)) as client:
        headers = {"x-matchlens-token": client.get("/api/session").json()["token"]}
        path = f"/api/matches/{mid}/sources/{source['id']}/annotations"
        assert client.get("/api/annotation-schema").json()["additionalProperties"] is False
        bundle = client.get(path).json()
        assert client.post(path + "?revision=0", headers=headers, json=bundle).status_code == 200
        assert client.post(path + "?revision=0", headers=headers, json=bundle).status_code == 400
        invalid = copy.deepcopy(bundle)
        invalid["frames"] = [{"time": 1, "objects": [{"id": "x", "box": [0, 0, 2, 1]}]}]
        assert client.post(path + "?revision=1", headers=headers, json=invalid).status_code == 422


def test_landmarks_and_tv_reference_round_trip_in_one_revision(store):
    import base64

    import cv2
    import numpy as np

    mid, source = source_fixture(store)
    bundle = export_annotations(store, mid, source["id"])
    points = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    bundle["field_calibrations"] = [
        {
            "source_id": source["id"],
            "image": points,
            "field": [[0, 0], [1, 0], [1, 1], [0, 1]],
        }
    ]
    _, encoded = cv2.imencode(".jpg", np.zeros((180, 320, 3), np.uint8))
    bundle["television"] = {
        "calibration": {"corners": points},
        "reference_image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode(),
    }
    import_annotations(store, mid, source["id"], AnnotationBundle.model_validate(bundle), 0)
    exported = export_annotations(store, mid, source["id"])
    assert exported["revision"] == 1
    assert exported["field_calibrations"][0]["image"] == points
    assert exported["television"]["calibration"]["corners"] == points
    assert exported["television"]["reference_image"].startswith("data:image/jpeg;base64,")
    store.undo(mid, 1)
    assert export_annotations(store, mid, source["id"])["television"] is None
