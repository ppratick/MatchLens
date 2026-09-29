# MatchLens engineering beta status

Implemented and locally exercised on 2026-09-29. This is an engineering beta with production-style separation and persistence, not a claim that all of the original long-term product plan is complete.

## Capability matrix

| Capability | Actual implementation | Boundary |
|---|---|---|
| Original video import and preservation | Working, checksummed copied original, separate proxy/poster | Corrupt/incomplete containers may be rejected |
| Local pretrained detection | YOLOX tiny ONNX person/sports-ball boxes; HOG fallback | Real soccer accuracy not measured; tiny/occluded ball is a known weakness |
| Player tracking | Time-aware Kalman + two-stage association; checkpoints; cut resets | No global re-ID, jersey OCR, guaranteed persistent identity, or cross-camera fusion |
| Teams and roles | Color-cluster hints; manual team/player/goalkeeper/official assignment | Named-team and official classification are not automatic |
| Field mapping | Four-corner and paired-landmark UI/API, explicit validity intervals, homography, visible-polygon limits | No automatic field-line/goal-structure detector; moving-camera calibration remains manual |
| Timeline and statistics | Confirmed goals/shots/passes/turnovers/saves/possession, score, unknown/contested possession, reviewed-player counts and observed time | Automatic proposals require human review; no exact distance/speed or xG |
| Event detection | Experimental ball-control proposals and opt-in goal suggestions from reviewed scoreboard increments plus replay evidence | No trained goal/shot/pass/save/turnover classifier; proposals never become facts automatically |
| Corrections | Drawn player/ball frame labels, checksummed annotation exchange, event/identity/team edits, field/TV calibration, exclusions, undo/redo | Identity split/link is a review alias/interval operation, not raw tracker retraining; raw track-list summaries are fragment-oriented |
| Video capture | Browser display/window picker, independent authenticated ingest/FFmpeg recording, audio availability, indexed devices and streams | Real hardware permissions/device behavior not tested; one active capture slot |
| Phone streaming | Separate HTTPS paired receiver, sender epochs, idempotent ordered chunks, health/status, manual TV alignment and movement guard | Requires trusted certificate and foreground phone; real iOS/Android not certified |
| Live UI | Recording/job status, buffered video, delayed analyzed frame, score/clock, events, field, quality observations | Saved-segment delay is measured; full sensor-to-screen latency and exact device frame drops are not |
| Backpressure/recovery | Bounded decode queue, analysis skip/downsample, checkpoints, independent recorder, restarted-worker detection | Recording cannot recover unavailable network frames or guarantee a power-loss tail |
| Highlights | Automatic clip queue on confirmed goal/shot/save; custom, exact, fast-copy, annotated, team/player reel | Export runs after capture; gap-crossing clips rejected; player reels rely on reviewed event names |
| Reports/data | Local HTML, JSON, CSV, printable PDF through browser; pinned revisions | No custom PDF engine or cloud publishing |
| Multi-match review | Library and two-match count/coverage comparison | No normalized longitudinal athlete model or comparable multi-season analytics |
| Multiple sources | Import/switch and explicit pre-analysis timeline offsets | No synchronized multi-camera capture/fusion |
| Additional sports | Shared interfaces and soccer plugin | Only soccer accepted in product schema today |
| Privacy/deletion | Local default, no login, same-origin/CSRF protections, managed-data deletion | OS backups/downloaded copies and physical secure erasure remain outside app control |

## Verified in this environment

- 52 backend domain/API/media tests and seven Playwright workflows pass. One upstream Starlette/httpx test-client deprecation warning remains; it is not a runtime test failure.
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
5. Evaluate automatic field recalibration, robust camera motion/cut/replay handling, better identity association and jersey hints. The optional CoreML path has measured short-run speed/placement/parity; full-corpus parity and live hardware validation remain gates.
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

## Source, capture, and evaluation milestones

Five explicit profiles are exposed via `/api/profiles`; sideline is **Coming later**. Later analysis runs no longer replace the selected version implicitly. Annotation exchange validates checksum, profile, offset, schema and review revision; TV references and field landmarks are included. Manual frame screenshots are synchronized to saved timestamps.

Five Playwright workflows pass: review/pinned exports/persistence, setup/creation, box labels and TV corners, generated screen capture, and generated phone-TV capture. Actual browser encoding and playable saved segments are exercised. Native Chrome annotation layout was inspected. Backend transport tests cover duplicate/reordered chunks, sender epoch mismatch, status and suspension; screen ingest is protected on loopback and rejected by the LAN phone receiver.

CoreML can be selected experimentally. Actual kernel placement, one-frame raw output parity, compilation/warmup, sustained short throughput and worker RSS are recorded in `validation/provider-comparison-synthetic.json`. CPU remains default. YOLOX Small now has a measured follow-up CPU/CoreML comparison; neither neural model has measured real-soccer accuracy. See evaluation for measured values and limits.

Live overload policy reduces sampling, disables overlays, skips stale analysis with intervals, then pauses inference in recording-only mode. Original video is never deleted to reduce latency. Buffer pauses/suspension have explicit unknown-boundary gaps; exports cannot silently concatenate those timelines. A full 120-minute hardware soak, true device frame-drop counts and sensor-to-screen latency remain unverified.

The corrected 180-second generated capture/actual YOLOX CPU soak preserved 91 playable, audio-containing segments and 181.355 seconds through an intentional inference crash, with no segment timeline gaps. This short engineering soak is not the full-match hardware gate. Raw measurements are committed without media in `validation/soak-synthetic-180s.json`. All automated writes remained in temporary libraries; the user's library was not modified.

## Broadcast review and fault checks

Six browser workflows pass, including opt-in goal suggestions from manually read scoreboard increments plus a separately marked replay. Score stays unchanged until human confirmation. Definitions, evidence rules and per-class evaluation gates are in `docs/EVENTS.md`; zero evaluated real-event samples means precision/recall/false positives remain unknown. New runs snapshot reviewed cuts/exclusions; cuts reset identities and control candidates and invalidate prior field mapping. Closeups/replays/non-play/unknown samples withhold inference. Automatic replay/OCR/shot/pass/save/turnover classifiers remain disabled.

47 backend tests now include actual variable-frame-rate PTS sampling, 4K input with bounded 2560-pixel analysis payloads, original preservation, truncated-copy rejection, manual-cut/exclusion processing, source-specific replay exclusions and goal-evidence recomputation/undo. Committed segments carry SHA-256; analysis refuses changed preserved segments. Recording resolution is unchanged.

The actual macOS disk-full harness mounted an owned 768 MiB temporary image. Capture stopped at the 512 MiB reserve, three earlier segments remained readable with unchanged hashes, and a later actual ENOSPC (errno 28) blocked derived writes. The image was detached; the host filesystem and user library were not filled or modified. Raw result: `validation/disk-fault-synthetic.json`.

## Setup and second detector milestone

The setup screen exposes all five source profiles and evaluation gates, FFmpeg/FFprobe availability, storage reserve, permission/recovery guidance, and local Tiny/Small ONNX import. Imports require the local session, are size-limited and shape-tested before replacing weights, and are serialized. Invalid files preserve previous weights; active jobs must finish or pause first. Both valid HTTP import and invalid import were checked against temporary storage. Native Chrome setup layout was inspected.

The follow-up provider matrix measured Tiny CPU/CoreML at 22.01/70.51 sampled frames/s and Small at 7.22/50.16 on the same synthetic fixture. Both runtime traces and single-frame parity checks passed. This establishes short engineering throughput, not soccer accuracy or a preferred detector. Earlier missing-Small rows are historical. Event editors display definitions and unvalidated evaluation counts directly.

Setup/provider milestone checks: 50 backend tests, seven Playwright workflows, Ruff lint/format, TypeScript, Vite build and frontend formatting pass. Browser tests include invalid ONNX import recovery and visible per-profile gates; a separate temporary localhost HTTP run successfully imported the official Small model.

## Sender recovery and spatial review milestone

Current checks: 52 backend tests, seven Playwright workflows, Ruff lint/format,
TypeScript, Vite production build, frontend and phone-sender formatting pass.
Native Chrome partial-landmark calibration layout was inspected in the isolated
library. Historical counts above describe their respective milestones.

Phone finalization now retries transient failures even after the upload queue
drains. A recording-worker failure prevents automatic capture resumption;
terminal receiver refusals retain the unsent queue with a raw-tail download.
The tail alone is not a complete playable recording. A reload cannot reuse a
pairing with an existing epoch, and closing before finalization warns the user.
The generated phone browser test interrupts both upload and finalization,
recovers to playable saved media, then verifies the used-epoch reload guard.

Field review supports at least four paired visible landmarks for partial views.
The default validity is one second from the paused media timestamp; users may
extend only through a verified stationary shot. Reviewed cuts invalidate older
spatial mappings immediately. Unknown possession retains explicitly contested
time as a visible subset and never assigns it to either team. Distance and speed
remain withheld. The browser suite saves partial-landmark calibration and runs
a full offline pass after generated live screen capture, verifying that selection
stays on the prior run until the user explicitly selects the new version.

Model imports now enforce the adapter's static float32 image input and 80-class
raw-grid output contract before inference. Both official Tiny and Small imports
passed against disposable storage. No real soccer labels, physical phone capture,
OS permission/audio certification, or 120-minute hardware soak were supplied.
