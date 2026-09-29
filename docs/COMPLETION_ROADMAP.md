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

## Progress after capture and review integration

Milestones 0–2 are implemented and checked. Milestones 3–4 have generated-browser transport/playback tests, TV geometry/movement tests, and manual desktop UI inspection; actual Mac picker permissions/audio and iPhone 17 Pro Max remain unverified. Milestone 6 has CPU/CoreML runtime traces, single-frame parity, warmup/throughput/RSS measurements and a configurable default-CPU path; alternative neural weights and labeled profile evaluation remain gates. Milestone 7 has a corrected 180-second audio/video recovery soak, five critical browser workflows and 40 backend tests. Milestone 5 and additional reliability/packaging work remain to be implemented; external validation does not excuse those independent tasks.

Milestone 5 now has reviewed scoreboard regions/score-clock evidence, opt-in two-signal goal suggestions, documented event definitions and unknown per-class metrics, reviewed cut/exclusion snapshots and human-only confirmation. OCR and additional event classifiers stay disabled pending evaluation. Milestone 7 now includes a real disk-reserve/ENOSPC test in a bounded disposable image, VFR timestamps, 4K payload limits, truncated-source rejection and six browser workflows; 47 backend tests pass.
