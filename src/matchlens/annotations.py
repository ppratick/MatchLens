"""Revisioned manual ground truth; normalized displayed-original coordinates."""

from __future__ import annotations

import base64
import hashlib
from typing import Literal

from pydantic import Field, model_validator

from .domain import Calibration, Event, StrictModel
from .geometry import calibrate
from .media import sha256
from .profiles import profile_id
from .storage import Store, encode
from .television import TelevisionCalibration, prepare_setup


class ObjectLabel(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["person", "ball"] = "person"
    box: list[float] = Field(min_length=4, max_length=4)
    team: Literal["home", "away", "unknown"] = "unknown"
    player: str = Field(default="", max_length=100)
    track_id: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def bounds(self):
        x1, y1, x2, y2 = self.box
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Box must be normalized ordered x1/y1/x2/y2")
        return self


class FrameLabel(StrictModel):
    time: float = Field(ge=0)
    sample_interval: float = Field(default=0.2, gt=0, le=10)
    observable: bool = True
    objects: list[ObjectLabel] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len({o.id for o in self.objects}) != len(self.objects):
            raise ValueError("Object identities must be unique within a frame")
        if not self.observable and self.objects:
            raise ValueError("Unobservable frame cannot contain factual objects")
        return self


class IntervalLabel(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    kind: Literal["camera_cut", "replay", "closeup", "non_play", "unknown", "contested"]
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Interval end must follow start")
        return self


class TelevisionLabel(StrictModel):
    calibration: TelevisionCalibration
    reference_image: str = Field(max_length=8 * 1024 * 1024)


class AnnotationBundle(StrictModel):
    schema_version: Literal["matchlens-annotations-1"] = "matchlens-annotations-1"
    coordinate_space: Literal["displayed_original_normalized"] = "displayed_original_normalized"
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_profile: Literal["broadcast", "screen", "phone_tv", "synthetic", "sideline"]
    source_offset: float = Field(default=0, ge=0)
    revision: int = Field(ge=0)
    frames: list[FrameLabel] = Field(default_factory=list, max_length=20000)
    intervals: list[IntervalLabel] = Field(default_factory=list, max_length=5000)
    events: list[Event] = Field(default_factory=list, max_length=5000)
    field_calibrations: list[Calibration] = Field(default_factory=list, max_length=100)
    television: TelevisionLabel | None = None

    @model_validator(mode="after")
    def unique(self):
        if len({f.time for f in self.frames}) != len(self.frames):
            raise ValueError("Annotation timestamps must be unique")
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError("Event IDs must be unique")
        return self


def source_checksum(store: Store, mid: str, source: dict) -> str:
    if source.get("status") == "recording":
        raise ValueError("Finalize the recording before exchanging annotations")
    if source.get("path"):
        actual = sha256(store.path(mid, source["path"]))
        if source.get("sha256") and actual != source["sha256"]:
            raise ValueError("Original source checksum changed")
        return actual
    segments = source.get("segments", [])
    if not segments:
        raise ValueError("Source has no preserved media")
    manifest = [
        {"start": s["start"], "end": s["end"], "sha256": sha256(store.path(mid, s["path"]))} for s in segments
    ]
    return hashlib.sha256(encode(manifest).encode()).hexdigest()


def export_annotations(store: Store, mid: str, sid: str) -> dict:
    source = store.source(mid, sid)
    revision, review = store.review(mid)
    saved = review.get("annotations", {}).get(sid, {})
    television = review.get("television", {}).get(sid)
    if television:
        reference = store.path(mid, television["reference"])
        if sha256(reference) != television["reference_sha256"]:
            raise ValueError("Television reference frame changed")
        television = {
            "calibration": {k: television[k] for k in TelevisionCalibration.model_fields},
            "reference_image": "data:image/jpeg;base64," + base64.b64encode(reference.read_bytes()).decode(),
        }
    return AnnotationBundle(
        source_sha256=source_checksum(store, mid, source),
        source_profile=profile_id(source, store.get(mid)["profile"]),
        source_offset=source.get("offset", 0),
        revision=revision,
        frames=saved.get("frames", []),
        intervals=saved.get("intervals", []),
        events=[e for e in review["events"].values() if e.get("source_id") == sid],
        field_calibrations=[
            {k: c[k] for k in Calibration.model_fields}
            for c in review["calibrations"]
            if c["source_id"] == sid
        ],
        television=television,
    ).model_dump()


def import_annotations(store: Store, mid: str, sid: str, bundle: AnnotationBundle, revision: int):
    if store.review(mid)[0] != revision:
        raise ValueError("Review revision changed; reload before importing")
    source = store.source(mid, sid)
    if bundle.source_sha256 != source_checksum(store, mid, source):
        raise ValueError("Annotation checksum does not match source")
    if bundle.source_profile != profile_id(source, store.get(mid)["profile"]):
        raise ValueError("Annotation profile does not match source; never pool profile results")
    if abs(bundle.source_offset - source.get("offset", 0)) > 1e-6:
        raise ValueError("Source alignment changed; annotation timestamps need explicit remapping")
    start, end = source.get("offset", 0), source.get("offset", 0) + source["duration"]
    if any(not start <= f.time < end for f in bundle.frames):
        raise ValueError("Annotation frame lies outside source")
    if any(not start <= i.start < i.end <= end + 0.1 for i in bundle.intervals):
        raise ValueError("Annotation interval lies outside source")
    if any(not start <= e.start <= (e.end or e.start) <= end + 0.1 for e in bundle.events):
        raise ValueError("Annotation event lies outside source")
    if any(c.source_id != sid or not start <= c.start < end for c in bundle.field_calibrations):
        raise ValueError("Field calibration belongs to another source or timeline")
    fields = [calibrate(c.model_dump()) for c in bundle.field_calibrations]
    television = prepare_setup(store, mid, sid, bundle.television.model_dump()) if bundle.television else None

    def transform(state):
        state.setdefault("annotations", {})[sid] = bundle.model_dump(
            exclude={"television", "field_calibrations"}
        )
        state["calibrations"] = [c for c in state["calibrations"] if c["source_id"] != sid] + fields
        if television:
            state.setdefault("television", {})[sid] = television
        else:
            state.setdefault("television", {}).pop(sid, None)
        for event in bundle.events:
            # Imported annotation events are reviewed/manual evidence, never model confirmation.
            existing = state["events"].get(event.id)
            if existing and existing.get("source_id") not in (None, sid):
                raise ValueError("Event ID belongs to another source")
            state["events"][event.id] = {**event.model_dump(), "source_id": sid}
        return state

    return store.edit(mid, revision, "annotation_import", transform)
