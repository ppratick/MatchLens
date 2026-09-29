# Implemented architecture

## Ownership and failure isolation

```text
Local React UI → localhost FastAPI → SQLite job supervisor
                                      ├─ recording worker → FFmpeg → closed media segments
                                      ├─ analysis worker → bounded decoder process → detector → tracker
                                      │                                             ↓
                                      │                                     frames/checkpoints/events
                                      └─ export worker → pinned review → FFmpeg / HTML / JSON / CSV

Optional phone HTTPS receiver → authenticated, ordered, durable spool → recording worker

Raw observations + immutable review history → effective match state → statistics / overlays / reports
```

One recording, one inference, and one export slot are scheduled globally. Exports wait during recording. The recorder does not share inference queues or memory. Workers are independent processes identified by PID **and process creation time**, so a server restart can reconnect without killing an unrelated reused PID. A single data-directory lock prevents multiple UI servers from scheduling duplicate work.

Decoding occurs in a spawned PyAV process with a four-frame bounded queue; the inference process owns OpenCV and ONNX Runtime. This also avoids duplicate bundled FFmpeg/Objective-C classes from PyAV/OpenCV in one macOS process. The decoder is stopped when its generator closes.

## Module boundaries

| Concern | Implementation | Contract |
|---|---|---|
| Configuration/privacy | `config.py` | Explicit managed data root; checked match IDs and paths |
| Source import/probing | `media.py` | Source manifest, original checksum, PTS/time base, separate proxy |
| Recording | `capture.py` | Publish only finalized, fsynced segments; independent FFmpeg child |
| Phone transport | `phone.py` | Expiring pairing capability, sequence/digest retry, committed byte offsets |
| Decode/buffering | `decoder.py` | Bounded `(timestamp, BGR frame, PTS, time_base)` stream |
| Detection | `vision.py`, `domain.Detector` | Normalized boxes, kind, score, optional appearance color |
| Tracking | `tracking.py` | Time-aware Kalman state, two-stage association, serializable checkpoint |
| Field projection | `geometry.py` | Versioned calibration interval; observed ground contact → normalized field |
| Sport rules/events | `sports.py`, `domain.SportPlugin` | Soccer event vocabulary, reviewed summaries, experimental control proposals |
| Pipeline | `pipeline.py` | Atomic batches of observations, proposals, and resumable tracker checkpoint |
| Match review | `review.py` | Validated correction commands, derived state, conservative statistics |
| Durable storage | `storage.py` | SQLite transactions/WAL, sources, jobs, raw runs, history DAG, export registry |
| Clips/reports | `exports.py` | Revision-pinned artifacts, media-gap checks, playable-output validation |
| Scheduling | `jobs.py`, `worker.py` | Bounded worker concurrency, cancellation, restart detection |
| API/UI | `api.py`, `apps/web` | Session-protected local writes, media ranges, review/playback/dashboard |
| Evaluation | `evaluation.py`, `tests` | Repeatable media fixtures and separately supplied accuracy annotations |

## Durable data layout

```text
MatchLens/
  library.sqlite                  # match index
  models/yolox_tiny.onnx + .json   # explicitly installed model and provenance
  pairing/                        # hashed, expiring phone capabilities
  matches/<match-id>/
    match.sqlite                  # sources/jobs/frames/proposals/history/audit/exports
    original/                     # copied originals; capture segments and phone received spool
    proxies/ thumbnails/          # replaceable playback artifacts
    exports/<export-id>/          # versioned media/report files and manifest
    temporary/ logs/ runs/
  deleting/                       # crash-recoverable deletion quarantine
  temporary/                      # bounded phone ingest staging
```

Frames use source PTS converted to seconds plus an explicit source offset, never frame-index/FPS time. Match-clock anchors are independent review state. A recording gap is not silently treated as observed footage. Multi-source alignment exists; automatic synchronization, cross-camera identity fusion, and simultaneous multi-camera capture do not.

## Correction and provenance semantics

- Raw runs are retained. One selected run per source drives current review. Starting/selecting another run changes revision; old track corrections remain tied to their old IDs and are not guessed onto new tracks.
- Corrections include events, interval-specific team/player/role assignment, alias-based identity splits/links, sampled ground-contact points, calibration, exclusions, and match-clock anchors.
- Edits append a state snapshot to a history DAG and increment revision under an optimistic concurrency check. Undo/redo selects a prior state; a new branch does not erase earlier history.
- Derived summaries are recalculated from raw observations plus review. Small UI snapshots are cached for three seconds, keyed by revision and job heartbeat. This implementation favors correctness over incremental recomputation; full-match review latency still needs measurement.
- Export jobs store the requested review snapshot and active-run mapping. Raw observations remain available for that run. Public job payloads deliberately omit recursive pinned snapshots and stream credentials.
- Model hash, source hash, detector name, pipeline version, sample rate, and checkpoint state are persisted. Resuming a checkpoint rejects changed provenance or a changed original file.
- Model confidence is not a calibrated probability of an event. Confirmed means reviewed, not independently verified ground truth. Unknown teams/possession and unobserved footage remain explicit.

## Backpressure and live behavior

The recorder is disk-first. Offline decoding blocks at its bounded queue. Live inference reads closed segments; when more than 12 seconds behind with multiple pending segments, it skips older analysis intervals, resets tracker continuity, and reduces sampling toward 2 fps. Skipped analysis is recorded in job metrics. It never deletes recorded segments to catch up.

The frontend polls every 2.5 seconds; an SSE status endpoint also exists. Buffered feed follows recent closed segments. Delayed-analysis mode displays the latest analyzed timestamp. These are short-buffer previews, not seamless low-latency streaming playback. An offline rerun fills skipped analysis later.

## Technology decisions and extension points

Python provides the modular processing API, with FFmpeg, NumPy, OpenCV, SciPy, and ONNX Runtime doing native work. YOLOX tiny is a small replaceable pretrained baseline. The tracker is custom and ByteTrack-inspired, **not** a claim to reproduce the official algorithm. CPU inference is the measured path; GPU providers are listed but not automatically selected.

SQLite and files avoid a required database server, Redis, cloud queue, or account. React/TypeScript and local assets provide the review application without introducing an Electron runtime. There is no native installer yet.

To add a detector, implement `Detector.detect` and register it in `detector_for`, then validate normalization and checkpoint provenance. To add a sport, implement its rules/summary plugin and add its event vocabulary, geometry, fixtures, and UI schema. The current validated request schema accepts soccer only; extension requires small integration changes, not replacing storage/capture/tracking infrastructure.

Do not move code to C++ merely because it is Python. First collect detector, association, decoding, serialization, disk, and UI timings on full matches. Native extension boundaries belong around measured hotspots, retaining the same message contracts.

## Frontend feature boundaries

`main.tsx` mounts `App.tsx`. `hooks/useWorkspace.ts` owns typed workspace coordination
and playback references; `features/` owns library, video, players, field,
statistics, timeline, exports, capture and setup views. Components declare the
workspace properties they consume. `shared/` contains constants and the accessible
modal shell. Ordered `styles/` imports retain the original cascade, with tokens,
shell, feature styles, motion, responsive rules, and live controls separated.

`npm run test:e2e` launches installed Chrome through Playwright and creates a new
temporary data root through `scripts/test_server.py`; it never reuses a server
pointing at the user's library.
