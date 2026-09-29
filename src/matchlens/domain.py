from __future__ import annotations

import time
import uuid
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid() -> str:
    return uuid.uuid4().hex


def now() -> float:
    return time.time()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MatchCreate(StrictModel):
    title: str = Field(min_length=1, max_length=150)
    home: str = Field(default="Home", min_length=1, max_length=60)
    away: str = Field(default="Away", min_length=1, max_length=60)
    sport: Literal["soccer"] = "soccer"
    profile: Literal["wide", "phone", "broadcast", "game", "synthetic"] = "wide"
    date: str = Field(default="", max_length=40)


class AnalysisRequest(StrictModel):
    source_id: str | None = None
    sample_fps: float = Field(default=5, ge=0.5, le=15)
    detector: Literal["yolox", "hog", "synthetic"] = "yolox"
    experimental_events: bool = False
    live: bool = False


class Event(StrictModel):
    id: str = Field(default_factory=uid)
    kind: Literal["goal", "shot", "pass", "turnover", "save", "possession", "note", "period"]
    start: float = Field(ge=0)
    end: float | None = Field(default=None, ge=0)
    team: Literal["home", "away", "unknown"] = "unknown"
    player: str = Field(default="", max_length=100)
    status: Literal["proposed", "confirmed", "rejected"] = "confirmed"
    note: str = Field(default="", max_length=2000)
    origin: Literal["manual", "model", "synthetic"] = "manual"
    evidence: str = Field(default="", max_length=2000)
    score: float | None = Field(default=None, ge=0, le=1)
    source_id: str | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.end is not None and self.end < self.start:
            raise ValueError("Event end must follow start")
        if self.kind == "possession" and (self.end is None or self.end <= self.start):
            raise ValueError("Possession needs a nonempty interval")
        return self


class Correction(StrictModel):
    revision: int = Field(ge=0)
    operation: Literal["event", "label", "calibration", "point", "exclude", "clock", "split", "merge"]
    payload: dict


class Label(StrictModel):
    track_id: str
    start: float = Field(default=0, ge=0)
    end: float = Field(default=1e9, gt=0)
    team: Literal["home", "away", "unknown"] = "unknown"
    player: str = Field(default="", max_length=100)
    role: Literal["player", "goalkeeper", "official", "ball", "unknown"] = "player"
    alias: str = Field(default="", max_length=100)


class Calibration(StrictModel):
    source_id: str
    start: float = Field(default=0, ge=0)
    end: float = Field(default=1e9, gt=0)
    image: list[list[float]] = Field(min_length=4, max_length=30)
    field: list[list[float]] = Field(min_length=4, max_length=30)
    length: float = Field(default=105, ge=20, le=130)
    width: float = Field(default=68, ge=15, le=100)
    dimensions_measured: bool = False


class ClipRequest(StrictModel):
    title: str = Field(default="Highlight", max_length=100)
    source_id: str | None = None
    start: float = Field(default=0, ge=0)
    end: float = Field(default=15, gt=0)
    event_ids: list[str] = Field(default_factory=list, max_length=300)
    team: Literal["home", "away", "all"] = "all"
    player: str = Field(default="", max_length=100)
    mode: Literal["exact", "copy", "reel", "annotated"] = "exact"
    pre: float = Field(default=10, ge=0, le=120)
    post: float = Field(default=5, ge=0, le=120)


class CaptureRequest(StrictModel):
    kind: Literal["stream", "screen", "camera", "test"]
    address: str = Field(default="", max_length=2048)
    device: str = Field(default="0:none", max_length=50)
    fps: int = Field(default=30, ge=1, le=60)
    analyze: bool = False
    detector: Literal["yolox", "hog"] = "yolox"


class Detection(StrictModel):
    box: list[float]
    score: float
    kind: Literal["person", "ball"] = "person"
    color: list[float] | None = None


class Detector(Protocol):
    name: str

    def detect(self, image) -> list[Detection]: ...


class SportPlugin(Protocol):
    name: str
    event_kinds: tuple[str, ...]

    def summarize(self, events: list[dict], duration: float, exclusions: list[dict]) -> dict: ...
