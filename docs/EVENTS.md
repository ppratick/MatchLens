# Soccer event review and evaluation gates

Every automatic result is a suggestion. Confirmed, nonexcluded timeline events
alone drive score, counts, clips and reports. Raw track IDs are fragments, not
verified people. Supporting evidence is visible in the event editor and retained
in revision-pinned JSON. Model confidence never means measured accuracy.

| Event | Definition | Automatic state | Evidence and review |
|---|---|---|---|
| Goal | Ball wholly crosses the goal line between posts and under crossbar; match context excludes replays/disallowed goals | Opt-in experimental reviewed-evidence rule | A +1 scoreboard increment within 120 seconds plus a separately marked replay starting within 45 seconds of the increment. No single cue suffices. Timestamp is evidence time; verify the actual goal instant, legality and team before confirming. No trained goal classifier is claimed. |
| Shot | Deliberate scoring attempt; blocked attempts count when intent is visible | Disabled | Human reviews attacking action and outcome; a fast moving ball alone is insufficient. |
| Possession | Team control over a nonempty play interval | Opt-in experimental ball-near-player proposals | Current motion/box proximity heuristic must be reviewed. Missing ball, unknown teams and competing ownership stay unknown; reviewed contested intervals do not imply a winner. |
| Turnover | A reviewed change of team control during play | Disabled | Verify control before/after; a cut or disappearance is insufficient. |
| Pass | Intentional transfer to a teammate with visible release and outcome | Disabled | Review passer, target, teams, release and reception/failed outcome. |
| Save | Goalkeeper intervention stopping an on-target attempt | Disabled | Review attempt direction and keeper action; ordinary catches are insufficient. |

For **each** class and source profile, evaluated sample count is currently **0**;
precision, recall and false-positive measurements are **unknown**, not zero.
`/api/event-definitions` exposes these definitions and gates. Offline
`evaluation.event_metrics` implements one-to-one same-class timestamp matching
with a declared tolerance and records precision/recall/TP/FP/FN. There is no
qualified real-event corpus. Release promotion requires independent held-out
matches, observable positives, non-event negatives, annotation revisions and
source checksums, per-class false positives per video hour, and review burden.
Do not pool phone-TV, screen, imported broadcast or synthetic measurements.

Scoreboard regions, manually read score/clock observations, replay/closeup/
non-play/unknown intervals travel with annotation exchange. Scoreboard evidence
does not set the match score. OCR is currently disabled; a local OCR adapter must
be evaluated for supported graphics before its output can be shown as reliable.
New analysis runs snapshot reviewed cuts/exclusions and reset tracks and control
candidates at cuts; replay/closeup/non-play/unknown inference is withheld. Cuts
invalidate older field calibration. Automatic thumbnail differences remain a
coarse unvalidated cut heuristic, not replay/shot recognition. Manual exclusions
can also be applied immediately to review without discarding any source video.
