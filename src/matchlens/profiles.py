"""Source-domain promises. Engineering fixtures never qualify another profile."""

from __future__ import annotations

PROFILES = {
    "broadcast": {
        "name": "Imported broadcast recording",
        "status": "engineering beta",
        "capabilities": ["preserved import", "offline tracks", "review", "clips and reports"],
        "preprocessing": ["display rotation", "PTS sampling", "cut resets", "manual replay exclusion"],
        "limitations": ["soccer accuracy unvalidated", "cuts break identity", "ball experimental"],
    },
    "screen": {
        "name": "Direct Mac screen capture",
        "status": "hardware validation required",
        "capabilities": ["independent recording", "delayed analysis", "offline pass", "review"],
        "preprocessing": ["PTS sampling", "cut resets", "manual replay exclusion"],
        "limitations": [
            "OS permission required",
            "audio depends on source/browser",
            "protected video may be blank",
        ],
    },
    "phone_tv": {
        "name": "Phone recording a television",
        "status": "iPhone 17 Pro Max unverified",
        "capabilities": [
            "paired HTTPS ingestion",
            "preserved received bytes",
            "television rectification",
            "review",
        ],
        "preprocessing": [
            "display rotation",
            "four-corner television warp",
            "movement checks",
            "PTS sampling",
        ],
        "limitations": [
            "trusted certificate and foreground required",
            "glare, flicker, moire and occlusion",
            "no device certification",
        ],
    },
    "synthetic": {
        "name": "Synthetic test footage",
        "status": "engineering fixture",
        "capabilities": ["deterministic demo", "transport and recovery tests", "scripted review labels"],
        "preprocessing": ["PTS sampling"],
        "limitations": ["not real soccer", "no transferable accuracy or compatibility result"],
    },
    "sideline": {
        "name": "Physical sideline recording",
        "status": "Coming later",
        "capabilities": [],
        "preprocessing": [],
        "limitations": ["not currently supported or evaluated"],
    },
}


def profile_id(source: dict, match_profile: str = "broadcast") -> str:
    explicit = source.get("profile")
    if explicit in PROFILES:
        return explicit
    if source.get("kind") == "phone":
        return "phone_tv"
    if source.get("kind") == "screen":
        return "screen"
    if source.get("kind") == "test" or match_profile == "synthetic":
        return "synthetic"
    # Legacy "wide", "phone", and "game" metadata are not certification.
    return {"phone": "phone_tv", "wide": "sideline"}.get(match_profile, "broadcast")


def profiles():
    return [
        {"id": key, **value, "evaluation": {"status": "not evaluated on labeled soccer", "sample_count": 0}}
        for key, value in PROFILES.items()
    ]
