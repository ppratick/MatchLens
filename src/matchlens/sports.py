from __future__ import annotations

from collections import Counter


def union_intervals(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


class Soccer:
    name = "soccer"
    event_kinds = ("goal", "shot", "pass", "turnover", "save", "possession", "note", "period")

    def summarize(self, events: list[dict], duration: float, exclusions: list[dict]) -> dict:
        confirmed = [e for e in events if e["status"] == "confirmed"]
        counts = {
            team: dict(Counter(e["kind"] for e in confirmed if e["team"] == team))
            for team in ("home", "away", "unknown")
        }
        possession = [e for e in confirmed if e["kind"] == "possession"]
        boundaries = {0.0, duration}
        for e in possession:
            boundaries.update([max(0, min(duration, e["start"])), max(0, min(duration, e["end"]))])
        for e in exclusions:
            boundaries.update([max(0, min(duration, e["start"])), max(0, min(duration, e["end"]))])
        times = sorted(boundaries)
        control = {"home": 0.0, "away": 0.0, "unknown": 0.0, "excluded": 0.0}
        contested_seconds = 0.0
        for a, b in zip(times, times[1:]):
            mid = (a + b) / 2
            if any(e.get("kind") != "contested" and e["start"] <= mid < e["end"] for e in exclusions):
                control["excluded"] += b - a
                continue
            owners = {e["team"] for e in possession if e["start"] <= mid < e["end"]}
            contested = len(owners - {"unknown"}) > 1 or any(
                e.get("kind") == "contested" and e["start"] <= mid < e["end"] for e in exclusions
            )
            owner = next(iter(owners)) if len(owners) == 1 and not contested else "unknown"
            if contested:
                contested_seconds += b - a
            control[owner] += b - a
        denominator = duration - control["excluded"]
        return {
            "method": "soccer-reviewed-v1",
            "counts": counts,
            "score": {team: counts[team].get("goal", 0) for team in ("home", "away")},
            "possession": {
                "seconds": control,
                "denominator": denominator,
                "contested_seconds": contested_seconds,
                "percent": {
                    t: round(control[t] / denominator * 100, 1) if denominator else None
                    for t in ("home", "away", "unknown")
                },
                "reliability": "reviewed intervals; overlapping contradictory labels are unknown",
            },
            "confirmed_events": len(confirmed),
            "proposed_events": sum(e["status"] == "proposed" for e in events),
            "count_scope": "confirmed timeline events; completeness has not been certified",
        }


SPORTS = {"soccer": Soccer()}


class SoccerCandidates:
    """Conservative experimental control transitions; never promotes a goal to fact.

    Outputs depend on observations, not scoreboard claims. Unknown teams are retained.
    No automatic shot/save/goal classifier is claimed by this baseline.
    """

    def __init__(self, state=None):
        self.state = state or {"owner": None, "candidate": None, "since": 0.0, "start": 0.0, "last": 0.0}

    def update(self, tracks: list[dict], timestamp: float, source_id: str, run_id: str) -> list[dict]:
        import hashlib
        import math

        balls = [t for t in tracks if t["kind"] == "ball" and t["score"] >= 0.5]
        people = [t for t in tracks if t["kind"] == "person"]
        owner = None
        if len(balls) == 1 and people:
            box = balls[0]["box"]
            ball = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
            distances = sorted(
                (math.dist(ball, [(p["box"][0] + p["box"][2]) / 2, p["box"][3]]), p["id"]) for p in people
            )
            if distances[0][0] < 0.035 and (len(distances) == 1 or distances[1][0] > distances[0][0] * 1.5):
                owner = distances[0][1]
        s = self.state
        if timestamp - s["last"] > 1:
            s.update(owner=None, candidate=None, start=timestamp, since=timestamp)
        s["last"] = timestamp
        if owner != s["candidate"]:
            s.update(candidate=owner, since=timestamp)
        result = []
        if timestamp - s["since"] >= 0.6 and owner != s["owner"]:
            if s["owner"] and timestamp - s["start"] >= 1:
                event_id = hashlib.sha256(f"{run_id}:{s['start']:.6f}:{s['owner']}".encode()).hexdigest()[:32]
                result.append(
                    {
                        "id": event_id,
                        "kind": "possession",
                        "start": s["start"],
                        "end": s["since"],
                        "team": "unknown",
                        "player": "",
                        "track_id": s["owner"],
                        "status": "proposed",
                        "origin": "model",
                        "note": "Possible control interval — review required",
                        "evidence": "Ball proximity, separation from other players and temporal persistence. Not validated control.",
                        "score": None,
                        "source_id": source_id,
                    }
                )
            s.update(owner=owner, start=s["since"])
        return result
