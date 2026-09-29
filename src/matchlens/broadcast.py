"""Reviewed broadcast evidence. No scoreboard cue establishes a factual goal."""

from __future__ import annotations

import hashlib
import json

from pydantic import Field, model_validator

from .domain import StrictModel


class ScoreObservation(StrictModel):
    time: float = Field(ge=0)
    home: int = Field(ge=0, le=99)
    away: int = Field(ge=0, le=99)
    clock: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=500)


class BroadcastReview(StrictModel):
    scoreboard: list[float] | None = Field(default=None, min_length=4, max_length=4)
    observations: list[ScoreObservation] = Field(default_factory=list, max_length=1000)
    goal_suggestions: bool = False

    @model_validator(mode="after")
    def valid(self):
        if self.scoreboard:
            x1, y1, x2, y2 = self.scoreboard
            if not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1:
                raise ValueError("Scoreboard region needs ordered normalized corners")
        if len({o.time for o in self.observations}) != len(self.observations):
            raise ValueError("Scoreboard observations need unique timestamps")
        return self


DEFINITIONS = {
    "goal": "Ball wholly crosses the goal line between posts and under the crossbar; reviewed match context must exclude replays and disallowed goals.",
    "shot": "A deliberate attempt to score; blocked attempts are shots when attacking intent is observable.",
    "possession": "Reviewed team control over a nonempty interval; unresolved, contested, and unobservable control stays unknown.",
    "turnover": "A reviewed change of team control during play; a camera cut or missing ball alone cannot establish it.",
    "pass": "An intentional transfer of the ball to a teammate with an observable release and outcome.",
    "save": "A goalkeeper intervention stopping an observable on-target attempt; an ordinary catch is insufficient.",
}


def event_catalog():
    return [
        {
            "kind": kind,
            "definition": definition,
            "automatic_status": "experimental, opt-in" if kind in ("goal", "possession") else "disabled",
            "reliability": "unvalidated; human review required",
            "sample_count": 0,
            "precision": None,
            "recall": None,
            "false_positives": None,
        }
        for kind, definition in DEFINITIONS.items()
    ]


def goal_candidates(source_id, setup, intervals):
    """A reviewed scoreboard increment plus separately marked replay proposes review only.

    Timestamp is scoreboard evidence time, not a claimed actual goal instant.
    No OCR, audio, replay classification or trained goal accuracy is implied.
    """
    if not setup.get("goal_suggestions"):
        return []
    observations = sorted(setup.get("observations", []), key=lambda o: o["time"])
    results = []
    for before, after in zip(observations, observations[1:]):
        delta = (after["home"] - before["home"], after["away"] - before["away"])
        if delta not in ((1, 0), (0, 1)) or after["time"] - before["time"] > 120:
            continue
        replay = next(
            (
                i
                for i in intervals
                if i["kind"] == "replay" and after["time"] <= i["start"] <= after["time"] + 45
            ),
            None,
        )
        if not replay:
            continue
        evidence = {
            "scoreboard_before": before,
            "scoreboard_after": after,
            "reviewed_replay": replay,
            "method": "reviewed-score-and-replay-v1",
        }
        identity = hashlib.sha256(
            f"{source_id}:{before['time']}:{after['time']}:{delta}".encode()
        ).hexdigest()[:32]
        results.append(
            {
                "id": identity,
                "kind": "goal",
                "start": after["time"],
                "end": None,
                "team": "home" if delta == (1, 0) else "away",
                "player": "",
                "status": "proposed",
                "origin": "model",
                "score": None,
                "source_id": source_id,
                "note": "Experimental review suggestion. Seek back to verify the actual goal, team, and legality before confirming; scoreboard evidence time is not goal time.",
                "evidence": json.dumps(evidence, sort_keys=True),
            }
        )
    return results
