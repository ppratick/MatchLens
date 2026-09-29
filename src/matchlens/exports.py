from __future__ import annotations

import csv
import html
import json
import subprocess

import cv2

from .domain import ClipRequest, now, uid
from .geometry import apply_review
from .media import probe, run_media
from .review import snapshot
from .sports import union_intervals
from .storage import Store, atomic_json, encode


def publish(store: Store, match_id: str, artifact: dict):
    with store.db(match_id) as db:
        db.execute("INSERT OR REPLACE INTO exports VALUES(?,?)", (artifact["id"], encode(artifact)))


def csv_safe(row):
    # Spreadsheet applications interpret formula-leading strings even in quoted CSV cells.
    return {
        k: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        for k, v in row.items()
    }


def report(store: Store, match_id: str, pinned_snapshot=None):
    data = pinned_snapshot or snapshot(store, match_id)
    export_id, revision = uid(), data["match"]["revision"]
    root = store.path(match_id, f"exports/{export_id}")
    root.mkdir()
    atomic_json(root / "match.json", {"schema": "matchlens-1", "exported": now(), **data})
    with (root / "events.csv").open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "kind", "start", "end", "team", "player", "status", "origin", "note"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(csv_safe(row) for row in data["events"])
    with (root / "tracks.csv").open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "kind", "team", "player", "start", "end", "observed_seconds", "samples"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(csv_safe(row) for row in data["tracks"])

    def esc(v):
        return html.escape(str(v))

    m, s = data["match"], data["statistics"]
    rows = "".join(
        f"<tr><td>{e['start']:.1f}s</td><td>{esc(e['kind'])}</td><td>{esc(e['team'])}</td><td>{esc(e['player'])}</td><td>{esc(e['status'])}</td><td>{esc(e['note'])}</td></tr>"
        for e in data["events"]
    )
    dots = "".join(
        f'<circle cx="{x * 630 + 10:.1f}" cy="{y * 400 + 10:.1f}" r="3" fill="{color}" opacity=".2"/>'
        for team, color in (("home", "#fc6d46"), ("away", "#588ff5"), ("unknown", "#aab4bf"))
        for x, y, _ in data["heatmap"][team]
    )
    field = f'<svg viewBox="0 0 650 420"><rect x="10" y="10" width="630" height="400" fill="#163e31" stroke="#d9e3dd"/><path d="M325 10V410" stroke="#d9e3dd"/><circle cx="325" cy="210" r="55" fill="none" stroke="#d9e3dd"/>{dots}</svg>'
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{esc(m["title"])} — MatchLens</title>
<style>body{{font:16px system-ui;color:#192522;max-width:1000px;margin:48px auto;padding:0 24px}}h1{{font-size:42px}}small,.muted{{color:#617068}}.score{{font-size:32px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid #ddd;text-align:left;padding:10px}}svg{{max-width:650px}}@media print{{button{{display:none}}}}.bar{{height:10px;background:#eee}}.fill{{height:100%;background:#e57842}}</style>
<p>MATCHLENS / LOCAL MATCH REPORT</p><h1>{esc(m["title"])}</h1><p>{esc(m["date"])} · Revision {revision} · {esc(m["profile"])}</p>
<p class="score">{esc(m["home"])} {s["score"]["home"]} — {s["score"]["away"]} {esc(m["away"])}</p>
<p>Score from confirmed timeline goals. {esc(s["count_scope"])}.</p>
<h2>Analysis coverage</h2><p>{s["coverage_percent"]}% of recording time represented by sampled analysis.</p>
<div class="bar"><div class="fill" style="width:{s["coverage_percent"]}%"></div></div>
<p>{esc(s["reliability"])}</p><h2>Reviewed statistics</h2><pre>{esc(json.dumps(s["counts"], indent=2))}</pre>
<p>Possession: {esc(json.dumps(s["possession"]["percent"]))}. Denominator: {s["possession"]["denominator"]:.1f}s. Unknown time is retained.</p>
<h2>Reviewed player summaries</h2><p>{esc(s.get("player_scope", "Reviewed identities only"))}</p><pre>{esc(json.dumps(s.get("players", []), indent=2))}</pre>
<h2>Observed positions</h2>{field}<p>{esc(s["spatial_note"])}</p>
<h2>Timeline</h2><table><thead><tr><th>Video time</th><th>Event</th><th>Team</th><th>Player</th><th>Review</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Provenance</h2><p>No media was uploaded to a cloud service. The accompanying JSON contains source hashes, analysis settings, review state, and model provenance.</p>
<p class="muted">Generated locally by MatchLens. Use your browser's Print → Save as PDF to share a PDF.</p></html>"""
    (root / "report.html").write_text(document)
    artifact = {
        "id": export_id,
        "kind": "report",
        "title": f"Match report · revision {revision}",
        "revision": revision,
        "created": now(),
        "files": {
            name: f"exports/{export_id}/{name}"
            for name in ("report.html", "match.json", "events.csv", "tracks.csv")
        },
    }
    atomic_json(root / "manifest.json", artifact)
    publish(store, match_id, artifact)
    return artifact


def source_parts(source: dict, start: float, end: float):
    segments = source.get("segments") or [
        {
            "path": source["path"],
            "start": source.get("offset", 0),
            "end": source.get("offset", 0) + source["duration"],
        }
    ]
    parts, covered = [], []
    for segment in segments:
        a, b = max(start, segment["start"]), min(end, segment["end"])
        if b > a:
            parts.append((segment["path"], a - segment["start"], b - segment["start"]))
            covered.append([a, b])
    total = sum(b - a for a, b in union_intervals(covered))
    if total < end - start - 0.15:
        raise ValueError(
            "Requested clip includes unavailable media or a recording gap. Trim it to available footage."
        )
    return parts


def clip(store: Store, match_id: str, job: dict):
    request = ClipRequest.model_validate(job["config"])
    data = job.get("snapshot") or snapshot(store, match_id)
    revision = data["match"]["revision"]
    source = store.source(match_id, request.source_id)
    if source.get("status") == "recording":
        raise ValueError("Clip is queued until recording is finalized")
    intervals = [[request.start, min(request.end, source["duration"] + source.get("offset", 0))]]
    if request.mode == "reel" or request.event_ids:
        events = [
            e
            for e in data["events"]
            if e["status"] == "confirmed"
            and not e.get("excluded")
            and (not request.event_ids or e["id"] in request.event_ids)
            and (request.team == "all" or e["team"] == request.team)
            and (not request.player or e["player"] == request.player)
            and (not e.get("source_id") or e["source_id"] == source["id"])
        ]
        intervals = union_intervals(
            [
                (
                    max(source.get("offset", 0), e["start"] - request.pre),
                    min(
                        source["duration"] + source.get("offset", 0),
                        (e.get("end") or e["start"]) + request.post,
                    ),
                )
                for e in events
            ]
        )
    if not intervals or any(b <= a for a, b in intervals):
        raise ValueError("No valid clip intervals. Confirm matching events first.")
    export_id = job["id"]
    root = store.path(match_id, f"exports/{export_id}")
    root.mkdir(exist_ok=True)
    parts = []
    for a, b in intervals:
        for path, start, end in source_parts(source, a, b):
            part = root / f"part-{len(parts):04d}.mp4"
            args = [
                store.settings.ffmpeg,
                "-v",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(store.path(match_id, path)),
                "-t",
                str(end - start),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
            ]
            if request.mode == "copy":
                args += ["-c", "copy"]
            else:
                args += [
                    "-vf",
                    "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
                    "-r",
                    "30",
                    "-c:v",
                    "libx264",
                    "-threads",
                    "2",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "21",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                ]
            args += ["-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(part)]
            run_media(args, max(120, (end - start) * 5))
            parts.append(part)
    dest = root / "highlight.mp4"
    if len(parts) == 1:
        parts[0].replace(dest)
    else:
        # Generated basenames only: no user-controlled concat directives.
        listing = root / "parts.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
        run_media(
            [
                store.settings.ffmpeg,
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(listing),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(dest),
            ],
            120,
        )
        for part in parts:
            part.unlink()
        listing.unlink()
    if request.mode == "annotated":
        if len(intervals) != 1 or len(source_parts(source, *intervals[0])) != 1:
            raise ValueError("Annotated export currently requires one continuous interval")
        annotate(store, match_id, dest, source, intervals[0][0], data["review"], data["active_runs"])
    meta = probe(dest, store.settings)
    run_media(
        [store.settings.ffmpeg, "-v", "error", "-i", str(dest), "-f", "null", "-"],
        max(120, meta["duration"] * 3),
    )
    artifact = {
        "id": export_id,
        "kind": "video",
        "title": request.title,
        "revision": revision,
        "created": now(),
        "duration": meta["duration"],
        "intervals": intervals,
        "mode": request.mode,
        "boundary_note": "Keyframe-aligned; boundaries may differ"
        if request.mode == "copy"
        else "Re-encoded at 30 fps",
        "files": {"highlight.mp4": f"exports/{export_id}/highlight.mp4"},
    }
    atomic_json(root / "manifest.json", artifact)
    publish(store, match_id, artifact)
    return artifact


def annotate(store, match_id, video, source, offset, review, active_runs):
    from .decoder import buffered_frames

    frames = iter(store.iter_frames(match_id, source["id"], active_runs))
    upcoming = next(frames, None)
    latest = None
    silent = video.with_name("overlay-silent.mp4")
    meta = probe(video, store.settings)
    proc = subprocess.Popen(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{meta['width']}x{meta['height']}",
            "-r",
            "30",
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(silent),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for local_time, image, _, _ in buffered_frames(video, 30):
            t = offset + local_time
            while upcoming and upcoming["time"] <= t:
                latest, upcoming = upcoming, next(frames, None)
            if latest and t - latest["time"] <= max(0.5, latest["sample_interval"] * 1.5):
                for track in apply_review(latest, review)["tracks"]:
                    h, w = image.shape[:2]
                    ratio = min(w / latest["width"], h / latest["height"])
                    sw, sh = latest["width"] * ratio, latest["height"] * ratio
                    px, py = (w - sw) / 2, (h - sh) / 2
                    x1, y1, x2, y2 = [
                        int(v * (sw if i % 2 == 0 else sh) + (px if i % 2 == 0 else py))
                        for i, v in enumerate(track["box"])
                    ]
                    color = (75, 126, 250) if track["team"] == "home" else (255, 165, 70)
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        image,
                        track["player"] or track["display_id"],
                        (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        1,
                    )
            proc.stdin.write(image.tobytes())
    finally:
        proc.stdin.close()
        if proc.wait(timeout=60):
            raise ValueError("Overlay encoder failed")
    merged = video.with_name("overlay.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(silent),
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(merged),
        ],
        60,
    )
    merged.replace(video)
    silent.unlink()
