# MatchLens 0.1 status

Implemented and locally exercised on 2026-09-29. This is an engineering beta with production-style separation and persistence, not a claim that all of the original long-term product plan is complete.

## Capability matrix

| Capability | Actual implementation | Boundary |
|---|---|---|
| Original video import and preservation | Working, checksummed copied original, separate proxy/poster | Corrupt/incomplete containers may be rejected |
| Local pretrained detection | YOLOX tiny ONNX person/sports-ball boxes; HOG fallback | Real soccer accuracy not measured; tiny/occluded ball is a known weakness |
| Player tracking | Time-aware Kalman + two-stage association; checkpoints; cut resets | No global re-ID, jersey OCR, guaranteed persistent identity, or cross-camera fusion |
| Teams and roles | Color-cluster hints; manual team/player/goalkeeper/official assignment | Named-team and official classification are not automatic |
| Field mapping | Four-corner UI and multi-landmark API, intervals, homography, visible-polygon limits | No automatic field-line/goal-structure detector; moving-camera calibration remains manual |
| Timeline and statistics | Confirmed goals/shots/passes/turnovers/saves/possession, score, unknown possession, reviewed-player counts and observed time | Events beyond control proposals require human entry/review; no exact distance/speed or xG |
| Event detection | Optional experimental ball-control interval proposals | No trained goal/shot/pass/save/turnover classifier; proposals never become facts automatically |
| Corrections | Event edits/rejection, interval identity/team/role edits, point fixes, calibration, exclusion, aliases, undo/redo | Identity split/link is a review alias/interval operation, not raw tracker retraining; raw track-list summaries are fragment-oriented |
| Video capture | Independent FFmpeg segmentation for macOS devices, stream URL, synthetic source | Real hardware permissions/device behavior not tested; one active capture slot |
| Phone streaming | Separate HTTPS paired receiver, ordered durable chunks, bounded browser buffer | Requires trusted certificate and foreground phone; real iOS/Android not certified |
| Live UI | Recording/job status, buffered video, delayed analyzed frame, score/clock, events, field, quality observations | Saved-segment delay is measured; full sensor-to-screen latency and exact device frame drops are not |
| Backpressure/recovery | Bounded decode queue, analysis skip/downsample, checkpoints, independent recorder, restarted-worker detection | Recording cannot recover unavailable network frames or guarantee a power-loss tail |
| Highlights | Automatic clip queue on confirmed goal/shot/save; custom, exact, fast-copy, annotated, team/player reel | Export runs after capture; gap-crossing clips rejected; player reels rely on reviewed event names |
| Reports/data | Local HTML, JSON, CSV, printable PDF through browser; pinned revisions | No custom PDF engine or cloud publishing |
| Multi-match review | Library and two-match count/coverage comparison | No normalized longitudinal athlete model or comparable multi-season analytics |
| Multiple sources | Import/switch and explicit pre-analysis timeline offsets | No synchronized multi-camera capture/fusion |
| Additional sports | Shared interfaces and soccer plugin | Only soccer accepted in product schema today |
| Privacy/deletion | Local default, no login, same-origin/CSRF protections, managed-data deletion | OS backups/downloaded copies and physical secure erasure remain outside app control |

## Verified in this environment

- 24 backend domain/API/media tests pass. One upstream Starlette/httpx test-client deprecation warning remains; it is not a runtime test failure.
- TypeScript checking and Vite production build pass.
- A real localhost end-to-end run generated and analyzed the 20-second synthetic fixture, produced 14 tracks, served HTTP range video, and exported a playable MP4 plus HTML/JSON/CSV.
- The same run showed score 0–1 and 85% sampled coverage after the fixture exclusion; these are scripted demonstration facts, not inferred real-match results.
- A real FFmpeg recording worker continued committing media after a separate analysis worker failed.
- Checkpoint resume matched uninterrupted sampled observations; changed provenance is rejected.
- Authenticated phone chunks were reconstructed into playable saved segments, with byte-identical received original data.
- Native Chrome desktop library/studio playback and layout were inspected; actual phone hardware, OS screen capture permissions, mobile layouts, and a full-match soak remain unverified.
- Browser correction test: rejected the synthetic goal, observed score change 0–1 → 0–0 and confirmed events 6 → 5, then Undo restored both values.
- Actual YOLOX throughput on the short fixture: 24.61 sampled frames/s, p95 inference+tracking 37.23 ms. Accuracy was not evaluated. See the machine-generated benchmark JSON.

## Next release priorities

1. Collect a consented real-match benchmark corpus and validate the current baseline before promising event accuracy. This requires footage/annotations, not just additional application code.
2. Test real phone HTTPS recording, stream disconnect/reconnection, OS capture permissions, and a 120-minute recording/analysis soak. Improve seamless multi-segment playback and exact gap/drop accounting from those measurements.
3. Train/adapt ball, official, goal/field landmark, and sport-event models against the corpus. Add conservative evidence-backed event proposals class by class with measured precision/recall and calibrated reliability.
4. Improve identity corrections into explicit fragment graphs and add reviewed player aggregates/track navigation across changing raw runs. Add comprehensive property-based tests.
5. Add automatic field recalibration, robust camera motion/cut/replay handling, better identity association, jersey hints, and optional accelerator providers after profiling.
6. Add installer/signing, schema migrations beyond version 1, full accessibility/device QA, backup tooling, larger-library performance, and operational hardening before calling it production-ready.
7. Only then expand to synchronized multi-camera fusion and additional sport plugins with their own datasets, geometry, rules, and release gates.

## Completion milestone 1 — frontend maintenance

Verified again September 29: baseline 24 backend tests and all existing checks
pass. Feature components now own library, playback, field, players, statistics,
timeline dialogs, captures, pairing, exports, and setup. Shared tokens and ordered
stylesheet imports preserve the exact production CSS hash. `main.tsx` is a small
entry point, with app coordination and a typed workspace hook kept separately.
No Tailwind, Redux, or new API-state dependency was necessary for this extraction.

Two Playwright workflows pass against a server that creates its own disposable
library. They cover synthetic playback, correction/undo/redo, a revision-consistent
report, persisted review after page reload, player inspection, setup, creation, and
dialog keyboard dismissal. Native Chrome and the actual localhost
analysis/media-range/MP4/HTML/JSON/CSV path were also rechecked using temporary
storage. Browser reload proves persisted HTTP state, not a process-restart test.
