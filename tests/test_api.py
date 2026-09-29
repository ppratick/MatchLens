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
