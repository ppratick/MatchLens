# Completion roadmap

September 29, 2026. Continue the existing beta; recording integrity, local storage,
PTS, bounded resources, review, and immutable provenance remain release rules.
Each milestone needs relevant tests, local UI inspection, measurements, truthful
status updates, and a commit. No remote push. All automation uses temporary data.

| Milestone | Deliverable | Exit evidence |
|---|---|---|
| 0 | Preserve baseline, audit status, initialize Git | 24 tests, Ruff, TypeScript, build, Prettier pass; temporary-library Chrome inspection; ignored data verified |
| 1 | Feature modules and shared design tokens | Same visual identity; small entry point; feature components/hooks; browser review and critical Playwright flows |
| 2 | Explicit per-source profiles, version selection, annotation exchange | Five profiles with separate evaluation gates; offline runs cannot replace live results implicitly; checksummed revisioned annotations round-trip |
| 3 | Screen/display/window selection and recording health | Permission denial guidance, independent durable capture, audio availability disclosure, bounded ingest, offline rerun, crash test |
| 4 | Television setup and reliable phone epochs | Four-corner rectification, movement invalidation, bounded retry, gaps, receiving/recording status; duplicate/reordered/disconnected transport tests |
| 5 | Broadcast review and conservative events | Cuts reset identities, exclusions and scoreboard region retained; event definitions/evidence/gates; spatial results disabled on invalid geometry |
| 6 | Repeatable detector/provider comparison | Same footage/checksum/config, per-class metrics, team unknown coverage, warmup/placement/parity/CPU-CoreML speed/RSS; CPU stays default absent evidence |
| 7 | Reliability and local release | VFR/ranges/corruption/deletion/resume/export tests; recording-analysis soak; doctor and reproducible launcher; storage/recovery docs |
| 8 | External validation | Real Mac picker/permissions/audio and iPhone 17 Pro Max HTTPS recording; labeled permitted soccer corpus; 120-minute hardware soak; measured accuracy and latency |

## Baseline audit

- `docs/STATUS.md` correctly states 24 backend tests and unvalidated real soccer,
  phone interoperability, screen permissions, and full-match performance.
- `PLAN.md` is an historical proposal, despite its stale “implementation has not
  started” header. This roadmap supersedes its source priorities: physical
  sideline recording is **Coming later**.
- `pipeline.py` automatically activates every new run, contradicting explicit
  live/final version selection. Fix before calling the offline pass review-safe.
- Phone sender currently calls itself a sideline camera, has no television setup,
  reports chunk receipts as recording, and loses wall-time gaps on buffer pause.
- AVFoundation index entry is not a visible display/window picker. No permission
  preflight or actual desktop-capture certification exists.
- CoreML provider availability is listed, but only CPU is selected and measured.
- Accuracy evaluator pools classes; profile and small-ball/team breakdowns are
  missing. No permitted real-match footage or ground truth is present.
- Frontend: 3,157 lines in `main.tsx`, 2,680 in `style.css`; Playwright dependency
  exists but no critical workflow suite exists.

## Validation gates requiring the user

1. **Mac:** Record 2 minutes of a locally permitted video with a visible clock
   and audible sync marker, first choosing a window then a display. Deny capture
   once, verify guidance, grant it manually, stop/restart analysis while recording,
   stop capture, decode all saved media, and run/select the offline version.
2. **iPhone 17 Pro Max:** Same trusted Wi-Fi, trusted local HTTPS certificate,
   landscape mount centered on the TV, rear camera, screen filling most of frame,
   all four corners visible, power connected, camera page foreground. Record
   5 minutes of permitted footage; briefly disconnect Wi-Fi, reconnect, pause,
   move the mount, and stop. Inspect source epochs/gaps, byte preservation,
   audio sync, movement warning, and rectified analysis.
3. **Accuracy:** Supply a permitted 10-minute wide-view broadcast and its phone-TV
   recording, kept outside Git. Label at least 100 shared timestamps with all
   visible player boxes, ball when observable, team/unknown labels, cuts/replays,
   screen corners, and events. These are a smoke set; held-out release evidence
   needs more independent sessions and event positives, without pooling profiles.
4. **Hardware soak:** After the short gates pass, capture and analyze for 120
   minutes. Measure complete media/PTS coverage, worker and decoder RSS, queue
   bounds, disk growth, delay percentiles and gaps. Synthetic tests qualify only
   engineering behavior, never device compatibility or soccer accuracy.

Optional SAM 2, Tauri, WebRTC, and alternative observation databases require a
measured improvement; do not add them solely to expand the stack.

## Current completion audit

Milestones 0–7 have engineering implementations, relevant automated checks,
desktop UI inspection, committed measurements and local commits. This does not
close milestone 8 or certify the product. Current checks are 55 backend tests,
seven Playwright workflows, Ruff lint/format, TypeScript, production build and
frontend/phone formatting. Every automated library was temporary.

| Definition-of-complete item | Current evidence | Remaining gate |
|---|---|---|
| 1. Mac capture with delayed analysis | Generated browser MediaRecorder → authenticated receiver → playable segments; live samples and separate offline pass; inference-crash soak | Actual display/window picker, permissions, available audio and recording continuity on this Mac |
| 2. iPhone-TV pairing/record/reconnect | Ordered idempotent chunks, sender epochs, upload/finalization retry, reload rejection, status/health/gaps tested | iPhone 17 Pro Max Safari, trusted HTTPS, Wi-Fi interruption, suspension and audio sync |
| 3. Rectified television image | Four-corner sender/review UI, perspective warp/inverse coordinates, static-surrounding movement guard tested | Physical TV glare/flicker/moire/occlusion and mount movement |
| 4. Offline tracks/teams/events/stats/clips/report | Synthetic and generated media workflows pass; explicit run selection; conservative evidence-backed suggestions and confirmed exports | Real-soccer usefulness and accuracy; unsupported event classes remain disabled |
| 5. Clear uncertainty | Profile limits, unknown/contested possession, experimental event definitions, Coming later sideline and withheld metric distances | Review wording during physical-device use |
| 6. Efficient corrections | Drawn boxes/ball, identity/team, events, exclusions, TV corners and partial-field landmark UI; revisioned exchange | Real correction-time baseline; no SAM 2 speedup claim |
| 7. Persisted consistent corrections | SQLite revisions, undo/redo, reopened store tests, browser reload, pinned report/export tests | Longer real-session recovery and backup usability |
| 8. Measured detection/tracking accuracy | Per-profile checksum-aware labels and precision/recall/identity/team harness; TV preprocessing, reviewed cuts/exclusions and annotation provenance retained | No permitted labeled real soccer footage exists yet; accuracy remains unknown |
| 9. CPU/CoreML measurements | Tiny, Small and HOG matrix; neural CPU/CoreML runtime placement, one-frame parity, first inference, short sustained speed and RSS | Full-corpus parity, controlled cold start and sustained live hardware validation; CPU stays default |
| 10. Measured integrity/delay/resources | 180-second generated audio/video soak survives analysis kill; bounded queue/overload tests; owned-volume ENOSPC test | Actual source latency/drop accounting, full-match resource stability and 120-minute hardware soak |
| 11. Critical automated workflows | 55 backend tests and seven actual browser workflows, including live/offline selection and retry recovery | Real OS permission prompts and phone browsers cannot be replaced by generated streams |
| 12. Reproducibility/history/demo | Preserved baseline, feature commits, launcher/doctor/model import, polished labeled synthetic demo and updated docs | Complete external release evidence before calling portfolio version finished |
| 13. Sideline Coming later | Profile and setup/source UI explicitly withhold current support | Future work only |
| 14. Free/local workflow | SQLite/files, local models, loopback administrative API, narrow paired receiver, no account/API subscription | Dependencies/models must be installed once; no cloud processing is required |

SAM 2 is deferred because no real correction-time baseline or labeled propagation
set is available. Tauri/WebRTC/DuckDB are deferred because no measured deficiency
justifies replacing the working launcher/transport/SQLite. These are deliberate
validation gates, not completed integrations. The next work is the short Mac and
phone procedures above, then a labeled permitted corpus and longer hardware soak.
