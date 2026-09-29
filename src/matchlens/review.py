from __future__ import annotations

import math

from .domain import Correction, Event, Label
from .geometry import apply_review, calibrate
from .sports import SPORTS, union_intervals
from .storage import Store


def correct(store: Store, match_id: str, command: Correction) -> int:
    p, op = command.payload, command.operation
    duration = store.get(match_id)["duration"]
    source_ids = {s["id"] for s in store.sources(match_id)}

    def transform(state):
        if op == "event":
            e = Event.model_validate(p).model_dump()
            if e["start"] > duration + 1 or (e["end"] is not None and e["end"] > duration + 1):
                raise ValueError("Event lies outside the recording")
            if e["source_id"] and e["source_id"] not in source_ids:
                raise ValueError("Unknown source")
            state["events"][e["id"]] = e
        elif op == "label":
            label = Label.model_validate(p).model_dump()
            if label["end"] <= label["start"]:
                raise ValueError("Invalid label interval")
            state["labels"].append(label)
        elif op == "calibration":
            if p["source_id"] not in source_ids:
                raise ValueError("Unknown source")
            state["calibrations"].append(calibrate(p))
        elif op == "point":
            point = p.get("point", [])
            if len(point) != 2 or not all(
                isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x <= 1 for x in point
            ):
                raise ValueError("Point must be normalized x/y")
            t = float(p["time"])
            if not math.isfinite(t) or not 0 <= t <= duration:
                raise ValueError("Invalid point time")
            state["points"].append({"track_id": str(p["track_id"]), "time": t, "point": point})
        elif op == "exclude":
            a, b = float(p["start"]), float(p["end"])
            if not 0 <= a < b <= duration + 0.1:
                raise ValueError("Exclusion must lie within recording")
            state["exclusions"].append(
                {
                    "start": a,
                    "end": b,
                    "reason": str(p.get("reason", "Excluded"))[:200],
                    "exclude_events": bool(p.get("exclude_events", True)),
                }
            )
        elif op == "clock":
            period, anchor, match_anchor = (
                int(p["period"]),
                float(p["media_anchor"]),
                float(p["match_anchor"]),
            )
            if (
                not 1 <= period <= 6
                or not 0 <= anchor <= duration
                or not math.isfinite(match_anchor)
                or match_anchor < 0
            ):
                raise ValueError("Invalid period clock")
            state["clock"] = {"period": period, "media_anchor": anchor, "match_anchor": match_anchor}
        elif op == "split":
            label = Label.model_validate(
                {
                    "track_id": p["track_id"],
                    "start": p["time"],
                    "alias": f"{p['track_id']}-split-{command.revision + 1}",
                }
            ).model_dump()
            state["labels"].append(label)
        elif op == "merge":
            ids = set(p["track_ids"])
            if not 2 <= len(ids) <= 20 or not p.get("player", "").strip():
                raise ValueError("Choose 2–20 fragments and a player identity")
            for frame in store.iter_frames(match_id):
                if len(ids & {t["id"] for t in frame["tracks"]}) > 1:
                    raise ValueError("Fragments overlap in time; cannot merge two visible people")
            for track_id in ids:
                state["labels"].append(
                    Label(
                        track_id=track_id,
                        player=p["player"],
                        team=p.get("team", "unknown"),
                        alias=p["player"],
                    ).model_dump()
                )
        return state

    return store.edit(match_id, command.revision, op, transform)


def effective_events(store: Store, match_id: str, state: dict) -> list[dict]:
    events = {e["id"]: e for e in store.proposals(match_id)}
    events.update(state["events"])
    result = []
    for event in events.values():
        event = dict(event)
        if event.get("track_id") and event["origin"] == "model":
            for label in state["labels"]:
                if label["track_id"] == event["track_id"] and label["start"] <= event["start"] < label["end"]:
                    event.update(team=label["team"], player=label["player"])
        if any(
            x.get("exclude_events", True) and x["start"] <= event["start"] < x["end"]
            for x in [
                *state["exclusions"],
                *[
                    i
                    for sid, bundle in state.get("annotations", {}).items()
                    for i in bundle.get("intervals", [])
                    if i["kind"] in ("replay", "closeup", "non_play", "unknown")
                    and event.get("source_id") == sid
                ],
            ]
        ):
            event["excluded"] = True
        result.append(event)
    return sorted(result, key=lambda e: (e["start"], e["id"]))


def snapshot(store: Store, match_id: str) -> dict:
    info = store.get(match_id)
    revision, state = store.review(match_id)
    events = effective_events(store, match_id, state)
    exclusions = list(state["exclusions"])
    if len(store.sources(match_id)) == 1:
        exclusions.extend(
            interval
            for bundle in state.get("annotations", {}).values()
            for interval in bundle.get("intervals", [])
            if interval["kind"] in ("replay", "closeup", "non_play", "unknown")
        )
    stats = SPORTS[info["sport"]].summarize(
        [e for e in events if not e.get("excluded")], info["duration"], exclusions
    )
    tracks, observed_intervals, warnings = {}, [], set()
    player_intervals = {}
    players = {}
    for event in events:
        if event["status"] == "confirmed" and not event.get("excluded") and event.get("player"):
            key = (event["team"], event["player"])
            entry = players.setdefault(
                key, {"player": key[1], "team": key[0], "counts": {}, "observed_seconds": 0}
            )
            entry["counts"][event["kind"]] = entry["counts"].get(event["kind"], 0) + 1
    for source in store.sources(match_id):
        for gap in source.get("gaps", []):
            warnings.add(
                f"Recording gap / interruption near {gap.get('after', 0):.1f}s: {gap.get('reason', 'unknown')}"
            )
    heatmap = {"home": [], "away": [], "unknown": []}
    for raw in store.iter_frames(match_id):
        frame = apply_review(raw, state)
        warnings.update(frame.get("warnings", []))
        if frame["excluded"]:
            continue
        step = frame.get("sample_interval", 0.2)
        observed_intervals.append((frame["time"], min(info["duration"], frame["time"] + step)))
        for t in frame["tracks"]:
            if t["player"]:
                key = (t["team"], t["player"])
                players.setdefault(
                    key, {"player": key[1], "team": key[0], "counts": {}, "observed_seconds": 0}
                )
                player_intervals.setdefault(key, []).append(
                    (frame["time"], min(info["duration"], frame["time"] + step))
                )
            entry = tracks.setdefault(
                t["id"],
                {
                    "id": t["id"],
                    "kind": t["kind"],
                    "start": frame["time"],
                    "end": frame["time"],
                    "observed_seconds": 0,
                    "samples": 0,
                    "player": "",
                    "team": "unknown",
                    "role": t["role"],
                    "path": [],
                    "color": t.get("color"),
                    "team_hint": t.get("team_hint", "unknown"),
                },
            )
            entry.update(end=frame["time"], player=t["player"], team=t["team"], role=t["role"])
            entry["observed_seconds"] += max(0, min(step, info["duration"] - frame["time"]))
            entry["samples"] += 1
            if t["field"] is not None and entry["samples"] % 5 == 1:
                point = [*t["field"], frame["time"]]
                if len(entry["path"]) < 1500:
                    entry["path"].append(point)
                if len(heatmap[t["team"]]) < 10000:
                    heatmap[t["team"]].append(point)
    for key, intervals in player_intervals.items():
        players[key]["observed_seconds"] = sum(b - a for a, b in union_intervals(intervals))
    coverage_seconds = sum(b - a for a, b in union_intervals(observed_intervals))
    stats.update(
        revision=revision,
        coverage_seconds=coverage_seconds,
        coverage_percent=round(100 * coverage_seconds / info["duration"], 1) if info["duration"] else 0,
        coverage_description="Time represented by sampled analysis, not guaranteed player or ball visibility",
        unique_tracks=len([t for t in tracks.values() if t["kind"] == "person"]),
        reliability="Assisted review. Computer-vision accuracy has not been validated on match footage.",
        distance=None,
        speed=None,
        spatial_note="Field positions are estimates. Distance/speed withheld until calibration and tracking are validated.",
        players=list(players.values()),
        player_scope="Reviewed names and events only. Observed seconds are not minutes played; overlapping fragments are unioned.",
    )
    return {
        "match": {**info, "revision": revision},
        "sources": store.sources(match_id),
        "review": state,
        "events": events,
        "statistics": stats,
        "tracks": list(tracks.values()),
        "heatmap": heatmap,
        "jobs": [public_job(j) for j in store.jobs(match_id)],
        "exports": store.exports(match_id),
        "warnings": sorted(warnings),
        "active_runs": store.active_runs(match_id),
    }


def public_job(job):
    """Never recursively embed pinned export snapshots or source credentials in reports/UI."""
    value = {
        k: v
        for k, v in job.items()
        if k not in ("snapshot", "checkpoint", "config", "pid", "process_created", "recorder_pid")
    }
    value["config"] = {
        k: v for k, v in job.get("config", {}).items() if k not in ("address", "pair_id", "spool")
    }
    if job.get("checkpoint"):
        value["checkpoint"] = {
            k: v
            for k, v in job["checkpoint"].items()
            if k in ("time", "frames", "fps", "skipped", "wall_seconds")
        }
    return value
