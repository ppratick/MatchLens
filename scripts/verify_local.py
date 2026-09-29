"""Exercise the running local server against its explicit synthetic demo only."""

import argparse
import json
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Explicit isolated localhost server")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=30) as client:
        session = client.get("/api/session").json()
        import tempfile
        from pathlib import Path

        directory = Path(session["data_dir"]).resolve()
        allowed = [Path("/private/tmp"), Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve()]
        if not any(directory.is_relative_to(root) and directory != root for root in allowed):
            raise ValueError("Verification requires a disposable library under a temporary directory")
        token = session["token"]
        client.headers["x-matchlens-token"] = token
        matches = client.get("/api/matches").json()
        demo = next((m for m in matches if m["profile"] == "synthetic"), None)
        if not demo:
            response = client.post("/api/demo")
            response.raise_for_status()
            demo = response.json()
        match_id = demo["id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            data = client.get("/api/matches/" + match_id).json()
            if data["sources"] and any(
                j["kind"] == "analysis" and j["status"] == "complete" for j in data["jobs"]
            ):
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Demo did not finish")
        source = data["sources"][0]
        ranged = client.get(f"/media/{match_id}/{source['id']}", headers={"Range": "bytes=0-99"})
        assert ranged.status_code == 206 and len(ranged.content) == 100
        report = client.post(f"/api/matches/{match_id}/report")
        report.raise_for_status()
        clip = client.post(
            f"/api/matches/{match_id}/clips",
            json={
                "source_id": source["id"],
                "title": "Verified demo clip",
                "start": 2,
                "end": 5,
                "mode": "exact",
            },
        )
        clip.raise_for_status()
        expected = {report.json()["id"], clip.json()["id"]}
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            data = client.get("/api/matches/" + match_id).json()
            jobs = [j for j in data["jobs"] if j["id"] in expected]
            if any(j["status"] == "failed" for j in jobs):
                raise AssertionError(jobs)
            if len(jobs) == 2 and all(j["status"] == "complete" for j in jobs):
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Exports did not finish")
        expected_artifacts = {j["result"]["id"] for j in jobs}
        checked = []
        for artifact in data["exports"]:
            if artifact["id"] in expected_artifacts:
                for filename in artifact["files"]:
                    result = client.get(f"/api/matches/{match_id}/exports/{artifact['id']}/{filename}")
                    assert result.status_code == 200 and len(result.content) > 0
                    checked.append(filename)
        assert {"highlight.mp4", "report.html", "match.json", "events.csv", "tracks.csv"} <= set(checked)
        print(
            json.dumps(
                {
                    "match_id": match_id,
                    "source_path": source["path"],
                    "score": data["statistics"]["score"],
                    "tracks": len(data["tracks"]),
                    "coverage": data["statistics"]["coverage_percent"],
                    "analysis": [j.get("metrics") for j in data["jobs"] if j["kind"] == "analysis"],
                    "verified_exports": sorted(expected_artifacts),
                    "downloaded_files": checked,
                    "range_requests": "passed",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
