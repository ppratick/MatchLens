"""macOS-only actual ENOSPC test on an owned 768 MiB temporary disk image."""

import argparse
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from matchlens.config import Settings
from matchlens.domain import MatchCreate
from matchlens.jobs import Supervisor
from matchlens.media import probe, sha256
from matchlens.storage import Store, atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise ValueError("This volume test requires macOS hdiutil")
    with tempfile.TemporaryDirectory(prefix="matchlens-disk-fault-") as directory:
        root = Path(directory)
        image, mount = root / "test.dmg", root / "volume"
        mount.mkdir()
        subprocess.run(
            [
                "hdiutil",
                "create",
                "-size",
                "768m",
                "-fs",
                "HFS+",
                "-volname",
                "MatchLens disposable fault test",
                str(image),
            ],
            check=True,
            capture_output=True,
        )
        attached = False
        supervisor = None
        try:
            subprocess.run(
                ["hdiutil", "attach", str(image), "-mountpoint", str(mount), "-nobrowse", "-noautoopen"],
                check=True,
                capture_output=True,
            )
            attached = True
            if (
                os.stat(mount).st_dev == os.stat(root).st_dev
                or shutil.disk_usage(mount).total > 800 * 1024**2
            ):
                raise ValueError("Refusing to fill anything except the bounded mounted image")
            settings = Settings.load(mount / "library")
            store = Store(settings)
            mid = store.create(MatchCreate(title="Disposable disk fault", profile="synthetic"))["id"]
            source = {
                "id": "disk-source",
                "kind": "test",
                "profile": "synthetic",
                "duration": 0,
                "offset": 0,
                "status": "recording",
                "segments": [],
                "name": "Generated disk fixture",
            }
            store.put_source(mid, source)
            supervisor = Supervisor(store)
            job = supervisor.enqueue(mid, "capture", {"source_id": source["id"], "kind": "test"})
            supervisor.start()
            deadline = time.monotonic() + 25
            while len(store.source(mid, source["id"])["segments"]) < 2:
                if time.monotonic() > deadline or store.job(mid, job["id"])["status"] == "failed":
                    raise AssertionError(store.job(mid, job["id"]))
                time.sleep(0.2)
            before = store.source(mid, source["id"])["segments"]
            hashes = {s["path"]: sha256(store.path(mid, s["path"])) for s in before}
            filler = mount / "owned-filler.bin"
            block = b"x" * (2 * 1024**2)
            written = 0
            with filler.open("wb", buffering=0) as out:
                while shutil.disk_usage(mount).free > 500 * 1024**2:
                    written += out.write(block)
                    assert written <= 800 * 1024**2
                os.fsync(out.fileno())
            deadline = time.monotonic() + 20
            while (
                store.job(mid, job["id"])["status"] not in ("failed", "complete")
                and time.monotonic() < deadline
            ):
                time.sleep(0.2)
            failed = store.job(mid, job["id"])
            assert failed["status"] == "failed" and "free space" in failed["error"]
            source = store.source(mid, source["id"])
            supervisor.stop_match(mid)
            supervisor.close()
            supervisor = None
            full_error = None
            with filler.open("ab", buffering=0) as out:
                try:
                    while written < 800 * 1024**2:
                        written += out.write(block)
                    raise AssertionError("Image did not report ENOSPC within its bounded size")
                except OSError as exc:
                    assert exc.errno == errno.ENOSPC
                    full_error = exc.errno
                # A failed 2 MiB allocation can leave smaller free extents.
                for size in (65536, 4096, 512):
                    try:
                        while written < 800 * 1024**2:
                            written += out.write(b"x" * size)
                    except OSError as exc:
                        assert exc.errno == errno.ENOSPC
            try:
                atomic_json(mount / "derived.json", {"fixture": "disk-full", "payload": "x" * 65536})
                raise AssertionError("A full-volume write unexpectedly succeeded")
            except OSError as exc:
                assert exc.errno == errno.ENOSPC
            # Free only the owned filler before reading/decoding and orderly detach.
            with filler.open("r+b") as out:
                out.truncate(0)
            assert all(sha256(store.path(mid, path)) == digest for path, digest in hashes.items())
            assert all(
                probe(store.path(mid, s["path"]), settings)["duration"] > 0 for s in source["segments"]
            )
            result = {
                "schema": "matchlens-disk-fault-1",
                "volume_bytes": 768 * 1024**2,
                "source_profile": "synthetic",
                "reserve_failure": failed["error"],
                "actual_enospc_errno": full_error,
                "segments_retained": len(source["segments"]),
                "prior_checksums_unchanged": True,
                "segments_probe": True,
                "user_library_touched": False,
            }
            atomic_json(args.output, result)
            print(json.dumps(result, indent=2))
        finally:
            if supervisor:
                supervisor.stop_match(mid)
                supervisor.close()
            if attached:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True, capture_output=True)


if __name__ == "__main__":
    main()
