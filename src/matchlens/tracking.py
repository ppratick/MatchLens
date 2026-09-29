from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / max(area, 1e-9)


class Tracker:
    """Two-stage high/low-confidence association with elapsed-time Kalman prediction.

    Inspired by ByteTrack's association policy; this is not its reference implementation.
    IDs are observations within a run, not verified people.
    """

    def __init__(self, prefix: str, state=None):
        self.prefix = prefix
        self.state = state or {"next_id": 1, "tracks": [], "last": 0, "palette": []}

    def reset(self):
        self.state["tracks"] = []

    @staticmethod
    def measurement(box):
        return np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2, box[2] - box[0], box[3] - box[1]])

    @staticmethod
    def box(x):
        return [x[0] - x[2] / 2, x[1] - x[3] / 2, x[0] + x[2] / 2, x[1] + x[3] / 2]

    def update(self, detections, timestamp):
        dt = max(0.001, timestamp - self.state["last"])
        self.state["last"] = timestamp
        active = [
            t for t in self.state["tracks"] if timestamp - t["seen"] < (0.8 if t["kind"] == "ball" else 2.0)
        ]
        F = np.eye(8)
        F[:4, 4:] = np.eye(4) * dt
        for track in active:
            track["x"] = F @ np.array(track["x"])
            track["P"] = F @ np.array(track["P"]) @ F.T + np.eye(8) * 0.0001 * dt
        observations = [d.model_dump() for d in detections]
        high = [i for i, d in enumerate(observations) if d["score"] >= 0.45]
        low = [i for i, d in enumerate(observations) if 0.12 <= d["score"] < 0.45]
        used, matched = set(), set()
        result = []
        for candidates in (high, low):
            available = [i for i in range(len(active)) if i not in used]
            if not available or not candidates:
                continue
            costs = np.ones((len(available), len(candidates))) * 1e3
            for row, ti in enumerate(available):
                for col, di in enumerate(candidates):
                    t, d = active[ti], observations[di]
                    if t["kind"] != d["kind"]:
                        continue
                    overlap = iou(self.box(t["x"]), d["box"])
                    distance = np.linalg.norm(t["x"][:2] - self.measurement(d["box"])[:2])
                    if overlap > 0.05 or distance < max(0.015, min(0.09, t["x"][3] * 0.6)):
                        costs[row, col] = 1 - overlap + distance
            rows, cols = linear_sum_assignment(costs)
            for row, col in zip(rows, cols):
                if costs[row, col] >= 1.05:
                    continue
                ti, di = available[row], candidates[col]
                t, d = active[ti], observations[di]
                H = np.eye(4, 8)
                S = H @ t["P"] @ H.T + np.eye(4) * 0.0004
                K = t["P"] @ H.T @ np.linalg.inv(S)
                t["x"] = t["x"] + K @ (self.measurement(d["box"]) - H @ t["x"])
                t["P"] = (np.eye(8) - K @ H) @ t["P"]
                t["seen"] = timestamp
                used.add(ti)
                matched.add(di)
                result.append(self.output(t, d))
        for di in high:
            if di in matched:
                continue
            d = observations[di]
            t = {
                "id": f"{self.prefix}-{self.state['next_id']}",
                "kind": d["kind"],
                "seen": timestamp,
                "x": np.r_[self.measurement(d["box"]), np.zeros(4)],
                "P": np.eye(8) * 0.01,
            }
            self.state["next_id"] += 1
            active.append(t)
            result.append(self.output(t, d))
        self.state["tracks"] = [{**t, "x": t["x"].tolist(), "P": t["P"].tolist()} for t in active]
        return result

    def output(self, track, detection):
        color = detection.get("color")
        hint = "unknown"
        if color is not None:
            palette = self.state["palette"]
            if not palette:
                palette.append(color)
            distances = [float(np.linalg.norm(np.array(color) - p)) for p in palette]
            if min(distances) > 85 and len(palette) < 2:
                palette.append(color)
                distances.append(0.0)
            if min(distances) < 100:
                hint = f"kit-{int(np.argmin(distances)) + 1}"
        return {**detection, "id": track["id"], "team_hint": hint, "association": "estimated"}
