from __future__ import annotations

import contextlib
import copy
import json
import os
import shutil
import sqlite3
from pathlib import Path

from .config import Settings
from .domain import MatchCreate, now, uid


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@contextlib.contextmanager
def connect(path: Path):
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA secure_delete=ON")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        with con:
            yield con
    finally:
        con.close()


def atomic_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as out:
        out.write(encode(value))
        out.flush()
        os.fsync(out.fileno())
    tmp.replace(path)


EMPTY_REVIEW = {
    "events": {},
    "labels": [],
    "calibrations": [],
    "points": [],
    "exclusions": [],
    "clock": {"period": 1, "media_anchor": 0, "match_anchor": 0},
}


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.initialize()
        self.library = settings.data_dir / "library.sqlite"
        with connect(self.library) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS matches(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
        self.recover_deletions()

    def recover_deletions(self):
        for path in (self.settings.data_dir / "deleting").iterdir():
            if path.is_dir() and len(path.name) == 32:
                with connect(self.library) as db:
                    db.execute("DELETE FROM matches WHERE id=?", (path.name,))
                shutil.rmtree(path)
        pairing = self.settings.data_dir / "pairing"
        if pairing.exists():
            known = {m["id"] for m in self.list()}
            for path in pairing.glob("*.json"):
                if json.loads(path.read_text()).get("match_id") not in known:
                    path.unlink(missing_ok=True)
                    path.with_suffix(".json.lock").unlink(missing_ok=True)

    def create(self, request: MatchCreate) -> dict:
        match_id = uid()
        info = {
            **request.model_dump(),
            "id": match_id,
            "created": now(),
            "updated": now(),
            "revision": 0,
            "duration": 0,
            "status": "empty",
        }
        root = self.settings.match_dir(match_id)
        root.mkdir(mode=0o700)
        for part in ("original", "proxies", "thumbnails", "runs", "exports", "temporary", "logs"):
            (root / part).mkdir()
        with connect(root / "match.sqlite") as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE sources(id TEXT PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,data TEXT NOT NULL);
                CREATE TABLE frames(run_id TEXT NOT NULL,time REAL NOT NULL,source_id TEXT NOT NULL,data TEXT NOT NULL,
                    PRIMARY KEY(run_id,time));
                CREATE INDEX frames_time ON frames(source_id,time);
                CREATE TABLE proposals(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,data TEXT NOT NULL);
                CREATE TABLE history(id INTEGER PRIMARY KEY,parent INTEGER,state TEXT NOT NULL);
                CREATE TABLE audit(id INTEGER PRIMARY KEY,created REAL NOT NULL,kind TEXT NOT NULL,data TEXT NOT NULL);
                CREATE TABLE exports(id TEXT PRIMARY KEY,data TEXT NOT NULL);
                PRAGMA user_version=1;
            """)
            db.execute("INSERT INTO history(id,parent,state) VALUES(0,NULL,?)", (encode(EMPTY_REVIEW),))
            for key, value in {"revision": 0, "head": 0, "redo": [], "active_runs": {}}.items():
                db.execute("INSERT INTO meta VALUES(?,?)", (key, encode(value)))
        with connect(self.library) as db:
            db.execute("INSERT INTO matches VALUES(?,?)", (match_id, encode(info)))
        return info

    def db(self, match_id: str):
        path = self.settings.match_dir(match_id) / "match.sqlite"
        if not path.exists():
            raise KeyError("Match not found")
        return connect(path)

    def list(self) -> list[dict]:
        with connect(self.library) as db:
            return sorted(
                [json.loads(r[0]) for r in db.execute("SELECT data FROM matches")],
                key=lambda r: r["created"],
                reverse=True,
            )

    def get(self, match_id: str) -> dict:
        self.settings.match_dir(match_id)
        with connect(self.library) as db:
            row = db.execute("SELECT data FROM matches WHERE id=?", (match_id,)).fetchone()
        if not row:
            raise KeyError("Match not found")
        info = json.loads(row[0])
        info["revision"] = self.review(match_id)[0]
        return info

    def update(self, match_id: str, **changes):
        with connect(self.library) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM matches WHERE id=?", (match_id,)).fetchone()
            if not row:
                raise KeyError("Match not found")
            data = json.loads(row[0])
            data.update(changes, updated=now())
            db.execute("UPDATE matches SET data=? WHERE id=?", (encode(data), match_id))

    def sources(self, match_id: str) -> list[dict]:
        with self.db(match_id) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM sources ORDER BY rowid")]

    def put_source(self, match_id: str, source: dict):
        with self.db(match_id) as db:
            db.execute("INSERT OR REPLACE INTO sources VALUES(?,?)", (source["id"], encode(source)))
        duration = max((s.get("duration", 0) + s.get("offset", 0) for s in self.sources(match_id)), default=0)
        self.update(match_id, duration=duration, status="ready")

    def source(self, match_id: str, source_id: str | None = None) -> dict:
        sources = self.sources(match_id)
        found = next((s for s in sources if source_id is None or s["id"] == source_id), None)
        if found is None:
            raise ValueError("Import or record a video first")
        return found

    def path(self, match_id: str, relative: str) -> Path:
        root = self.settings.match_dir(match_id).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Path outside match")
        return path

    @staticmethod
    def meta(db, key: str):
        return json.loads(db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0])

    @staticmethod
    def set_meta(db, key: str, value):
        db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, encode(value)))

    def review(self, match_id: str) -> tuple[int, dict]:
        with self.db(match_id) as db:
            db.execute("BEGIN")
            head = self.meta(db, "head")
            state = json.loads(db.execute("SELECT state FROM history WHERE id=?", (head,)).fetchone()[0])
            return self.meta(db, "revision"), state

    def edit(self, match_id: str, revision: int, operation: str, transform):
        with self.db(match_id) as db:
            db.execute("BEGIN IMMEDIATE")
            if self.meta(db, "revision") != revision:
                raise ValueError("Review changed; refresh before applying this edit")
            head = self.meta(db, "head")
            state = json.loads(db.execute("SELECT state FROM history WHERE id=?", (head,)).fetchone()[0])
            result = transform(copy.deepcopy(state))
            cur = db.execute("INSERT INTO history(parent,state) VALUES(?,?)", (head, encode(result)))
            self.set_meta(db, "head", cur.lastrowid)
            self.set_meta(db, "redo", [])
            self.set_meta(db, "revision", revision + 1)
            db.execute(
                "INSERT INTO audit(created,kind,data) VALUES(?,?,?)",
                (now(), operation, encode({"revision": revision + 1})),
            )
        return revision + 1

    def undo(self, match_id: str, revision: int, redo=False):
        with self.db(match_id) as db:
            db.execute("BEGIN IMMEDIATE")
            if self.meta(db, "revision") != revision:
                raise ValueError("Review changed; refresh first")
            head, stack = self.meta(db, "head"), self.meta(db, "redo")
            if redo:
                if not stack:
                    raise ValueError("Nothing to redo")
                target = stack.pop()
            else:
                target = db.execute("SELECT parent FROM history WHERE id=?", (head,)).fetchone()[0]
                if target is None:
                    raise ValueError("Nothing to undo")
                stack.append(head)
            self.set_meta(db, "head", target)
            self.set_meta(db, "redo", stack)
            self.set_meta(db, "revision", revision + 1)
            db.execute(
                "INSERT INTO audit(created,kind,data) VALUES(?,?,?)",
                (now(), "redo" if redo else "undo", encode({"revision": revision + 1})),
            )
        return revision + 1

    def put_job(self, match_id: str, job: dict):
        with self.db(match_id) as db:
            db.execute(
                "INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)",
                (job["id"], job["kind"], job["status"], encode(job)),
            )

    def jobs(self, match_id: str) -> list[dict]:
        with self.db(match_id) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM jobs ORDER BY rowid DESC")]

    def job(self, match_id: str, job_id: str) -> dict:
        return next(j for j in self.jobs(match_id) if j["id"] == job_id)

    def active_runs(self, match_id: str) -> dict:
        with self.db(match_id) as db:
            return self.meta(db, "active_runs")

    def activate(self, match_id: str, source_id: str, run_id: str):
        with self.db(match_id) as db:
            db.execute("BEGIN IMMEDIATE")
            runs = self.meta(db, "active_runs")
            changed = runs.get(source_id) != run_id
            runs[source_id] = run_id
            self.set_meta(db, "active_runs", runs)
            if changed:
                self.set_meta(db, "revision", self.meta(db, "revision") + 1)
                db.execute(
                    "INSERT INTO audit(created,kind,data) VALUES(?,?,?)",
                    (now(), "select_analysis", encode({"source_id": source_id, "run_id": run_id})),
                )

    def frames(
        self,
        match_id: str,
        start: float = 0,
        end: float = 1e9,
        source_id: str | None = None,
        limit: int = 2000,
    ) -> list[dict]:
        runs = self.active_runs(match_id)
        if source_id:
            runs = {source_id: runs[source_id]} if source_id in runs else {}
        if not runs:
            return []
        with self.db(match_id) as db:
            q = (
                "SELECT data FROM frames WHERE run_id IN ("
                + ",".join("?" for _ in runs)
                + ") AND time>=? AND time<=? ORDER BY time LIMIT ?"
            )
            return [json.loads(r[0]) for r in db.execute(q, (*runs.values(), start, end, limit))]

    def iter_frames(self, match_id: str, source_id: str | None = None, runs: dict | None = None):
        runs = self.active_runs(match_id) if runs is None else runs
        if source_id:
            runs = {source_id: runs[source_id]} if source_id in runs else {}
        if not runs:
            return
        with self.db(match_id) as db:
            q = "SELECT data FROM frames WHERE run_id IN (" + ",".join("?" for _ in runs) + ") ORDER BY time"
            for row in db.execute(q, tuple(runs.values())):
                yield json.loads(row[0])

    def proposals(self, match_id: str) -> list[dict]:
        runs = set(self.active_runs(match_id).values())
        with self.db(match_id) as db:
            return [json.loads(r[1]) for r in db.execute("SELECT run_id,data FROM proposals") if r[0] in runs]

    def exports(self, match_id: str) -> list[dict]:
        with self.db(match_id) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM exports ORDER BY rowid DESC")]

    def delete(self, match_id: str):
        root = self.settings.match_dir(match_id)
        self.get(match_id)
        destination = self.settings.data_dir / "deleting" / match_id
        root.rename(destination)
        with connect(self.library) as db:
            db.execute("DELETE FROM matches WHERE id=?", (match_id,))
        with connect(self.library) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.rmtree(destination)
        pairing = self.settings.data_dir / "pairing"
        if pairing.exists():
            for path in pairing.glob("*.json"):
                if json.loads(path.read_text()).get("match_id") == match_id:
                    path.unlink()
                    path.with_suffix(".json.lock").unlink(missing_ok=True)
