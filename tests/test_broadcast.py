import copy

from matchlens.broadcast import BroadcastReview, event_catalog, goal_candidates
from matchlens.domain import Correction
from matchlens.review import correct, effective_events, snapshot


def evidence():
    return BroadcastReview(
        observations=[{"time": 1, "home": 0, "away": 0}, {"time": 5, "home": 1, "away": 0}],
        goal_suggestions=True,
    ).model_dump()


def test_goal_requires_two_reviewed_signals_and_opt_in():
    replay = [{"kind": "replay", "start": 8, "end": 10}]
    setup = evidence()
    assert goal_candidates("source", setup, []) == []
    assert goal_candidates("source", {**setup, "goal_suggestions": False}, replay) == []
    result = goal_candidates("source", setup, replay)
    assert len(result) == 1 and result[0]["status"] == "proposed"
    assert result[0]["score"] is None and result[0]["team"] == "home"
    assert "scoreboard_before" in result[0]["evidence"] and "reviewed_replay" in result[0]["evidence"]
    assert goal_candidates("source", setup, replay)[0]["id"] == result[0]["id"]
    invalid = copy.deepcopy(setup)
    invalid["observations"][1]["home"] = 3
    assert goal_candidates("source", invalid, replay) == []
    assert all(x["sample_count"] == 0 and x["precision"] is None for x in event_catalog())


def test_scoreboard_evidence_never_updates_score_without_confirmation(store, match):
    def setup(state):
        state["annotations"] = {
            "source": {"broadcast": evidence(), "intervals": [{"kind": "replay", "start": 8, "end": 10}]}
        }
        return state

    store.edit(match, 0, "fixture", setup)
    state = store.review(match)[1]
    proposal = effective_events(store, match, state)[0]
    assert snapshot(store, match)["statistics"]["score"]["home"] == 0
    correct(
        store,
        match,
        Correction(
            revision=1,
            operation="event",
            payload={**proposal, "source_id": None, "status": "confirmed", "start": 4},
        ),
    )
    assert snapshot(store, match)["statistics"]["score"]["home"] == 1
    store.undo(match, 2)
    assert snapshot(store, match)["statistics"]["score"]["home"] == 0


def test_replay_exclusion_does_not_contaminate_another_source(store, match):
    def setup(state):
        state["annotations"] = {"camera-a": {"intervals": [{"kind": "replay", "start": 1, "end": 5}]}}
        state["events"] = {
            "event": {
                "id": "event",
                "kind": "goal",
                "start": 3,
                "source_id": "camera-b",
                "origin": "manual",
                "status": "confirmed",
                "team": "home",
            }
        }
        return state

    store.edit(match, 0, "fixture", setup)
    assert not effective_events(store, match, store.review(match)[1])[0].get("excluded")
