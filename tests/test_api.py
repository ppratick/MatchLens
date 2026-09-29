from fastapi.testclient import TestClient

from matchlens.api import create_app


def test_local_session_and_csrf(store):
    with TestClient(create_app(store.settings, testing=True)) as client:
        assert client.post("/api/matches", json={"title": "x"}).status_code == 403
        token = client.get("/api/session").json()["token"]
        headers = {"x-matchlens-token": token}
        response = client.post("/api/matches", headers=headers, json={"title": "A match"})
        assert response.status_code == 201
        mid = response.json()["id"]
        assert client.get("/api/matches/" + mid).json()["statistics"]["coverage_percent"] == 0
        assert client.get("/api/matches", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/session", headers={"Host": "evil.example"}).status_code == 403
        assert client.get("/api/matches/" + mid + "/exports/bad/match.sqlite").status_code == 404
        assert client.delete("/api/matches/" + mid, headers=headers).status_code == 200
        assert client.get("/api/matches/" + mid).status_code == 404


def test_synthetic_detector_cannot_run_on_user_footage(store, match):
    store.put_source(match, {"id": "camera", "duration": 20, "path": "original/test.mp4"})
    with TestClient(create_app(store.settings, testing=True)) as client:
        token = client.get("/api/session").json()["token"]
        response = client.post(
            f"/api/matches/{match}/analyze",
            headers={"x-matchlens-token": token},
            json={"detector": "synthetic"},
        )
        assert response.status_code == 400


def test_paired_receiver_retry_and_finish(store, match):
    from matchlens.jobs import Supervisor
    from matchlens.phone import create_pair, receiver_app

    supervisor = Supervisor(store)
    pair = create_pair(store, supervisor, match)
    app = receiver_app(store.settings)
    with TestClient(app) as client:
        path = "/ingest/" + pair["pair_id"] + "/0"
        assert client.post(path, content=b"abc").status_code == 403
        headers = {"x-pair-secret": pair["secret"]}
        assert client.post(path, headers=headers, content=b"abc").status_code == 200
        assert client.post(path, headers=headers, content=b"abc").json()["duplicate"]
        assert client.post(path, headers=headers, content=b"xyz").status_code == 409
        assert client.post("/finish/" + pair["pair_id"], headers=headers).status_code == 200


def test_phone_epoch_reordering_status_and_suspension(store, match):
    from matchlens.jobs import Supervisor
    from matchlens.phone import create_pair, receiver_app

    pair = create_pair(store, Supervisor(store), match)
    with TestClient(receiver_app(store.settings)) as client:
        headers = {"x-pair-secret": pair["secret"], "x-sender-epoch": "camera-session-A"}
        status = f"/status/{pair['pair_id']}"
        assert client.get(status).status_code == 403
        assert client.get("/api/matches", headers=headers).status_code == 404
        # Missing/reordered chunk never advances durable sequence or bytes.
        assert (
            client.post(f"/ingest/{pair['pair_id']}/1", headers=headers, content=b"later").status_code == 409
        )
        assert (
            client.post(f"/ingest/{pair['pair_id']}/0", headers=headers, content=b"first").status_code == 200
        )
        assert client.get(status, headers=headers).json()["bytes"] == 5
        # Same sender resumes retry after a disconnect; a new MediaRecorder is refused.
        assert client.post(f"/ingest/{pair['pair_id']}/0", headers=headers, content=b"first").json()[
            "duplicate"
        ]
        different = {**headers, "x-sender-epoch": "camera-session-B"}
        assert (
            client.post(
                f"/ingest/{pair['pair_id']}/1", headers=different, content=b"new container"
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/health/{pair['pair_id']}", headers=headers, json={"state": "suspended", "elapsed_ms": 4000}
            ).status_code
            == 200
        )
        assert client.post(f"/finish/{pair['pair_id']}", headers=headers).status_code == 200
        assert (
            client.post(f"/ingest/{pair['pair_id']}/1", headers=headers, content=b"after finish").status_code
            == 409
        )
        assert client.get(status, headers=headers).json()["finished"]


def test_screen_ingest_is_loopback_session_protected_not_lan(store, match):
    from matchlens.phone import receiver_app

    with TestClient(create_app(store.settings, testing=True)) as client:
        token = client.get("/api/session").json()["token"]
        headers = {"x-matchlens-token": token}
        pair = client.post(f"/api/matches/{match}/screen-pair", headers=headers).json()
        sender = {**headers, "x-pair-secret": pair["secret"], "x-sender-epoch": "screen-A"}
        assert (
            client.post(
                f"/screen-ingest/ingest/{pair['pair_id']}/0", headers=sender, content=b"screen bytes"
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/screen-ingest/ingest/{pair['pair_id']}/1",
                headers={"x-pair-secret": pair["secret"]},
                content=b"unauthenticated",
            ).status_code
            == 403
        )
    with TestClient(receiver_app(store.settings)) as lan:
        assert (
            lan.post(
                f"/ingest/{pair['pair_id']}/1",
                headers={"x-pair-secret": pair["secret"]},
                content=b"must refuse",
            ).status_code
            == 403
        )
