# Evaluation and release gates

## Engineering fixtures that exist

Fixtures are generated locally using fixed parameters. They do not contain third-party match footage. Each accuracy annotation file must match its video's SHA-256.

| Fixture / test | Expected result |
|---|---|
| 20 s synthetic demo, 960×540, 30 fps | 100 analyzed samples at 5 fps; 14 stable colored-person tracks; confirmed home 0 / away 1; 85% sampled coverage after 12–15 s exclusion |
| Scripted demo possession | Home 6 s, away 6 s, unknown 5 s, excluded 3 s; 35.3% / 35.3% / 29.4% of 17 s eligible time |
| 6 s FFmpeg testsrc2 + sine | 30 analyzed samples at 5 fps; paused after 10 samples then resumed output equals uninterrupted output after run-ID normalization |
| Exact 1–3 s clip | Duration 2 s within one 30 fps frame plus mux tolerance; playable output; original checksum unchanged |
| Corrupt MP4 | Rejected, input bytes unchanged |
| Missing segment between 5–8 s | Clip crossing gap rejected |
| Real recording subprocess + failing inference worker | Capture commits additional segments after analysis fails; committed segments probe successfully |
| Phone WebM split into 16 KiB HTTP chunks | Auth enforced, ordered retries idempotent, 6 s stream yields at least three playable segments; received original bytes unchanged |
| Rotation metadata | 320×180 encoded picture with 90° display rotation decodes to 180×320 displayed geometry |
| Revision-pinned report | Subsequent confirmed goal does not change an older requested report; public jobs do not recursively contain export snapshots |
| Changed resume provenance | Resume fails explicitly rather than mixing pipeline/model versions |

Domain tests also cover contradictory possession, overlapping intervals, rejected events, undo/redo branching, revision conflicts, low-confidence association, missing observations, calibrated-polygon bounds, camera-cut invalidation, matching metrics, and managed-path deletion boundaries. API tests cover origin/host/session checks and export whitelisting. See executable tests for precise assertions.

## Current measured result

`validation/synthetic-yolox.json` records YOLOX tiny CPU inference/tracking on the 20-second synthetic fixture on the local M2 Pro:

- 100 sampled frames, 4.064 seconds wall time, 24.61 processed frames/s.
- Inference + tracking: p50 36.51 ms, p95 37.23 ms, p99 38.12 ms.
- Peak sampled inference-worker RSS: 194.1 MiB. This does not include every child/server/browser process.
- Accuracy: **not evaluated**. Synthetic geometric players are not a real-match accuracy set.
- Recording drops: **not measured by this offline benchmark**.

These are observations from one short run, not a performance guarantee. Re-run on representative long recordings after model/pipeline changes. The synthetic-color detector's higher throughput is only an engineering-fixture result and must never be marketed as neural soccer inference speed.

## Bring a real benchmark corpus

Real-match footage and annotations were not provided. Before claiming soccer accuracy, obtain recordings with permission and create a frozen corpus containing broadcast wide views, partial fields, small distant balls, similar kits, officials, shadows, night lighting, occlusion, camera motion, broadcasts/replays, and game-screen captures. Keep all frames from a match in one split; split by venue/camera/team/day to avoid leakage. Keep broadcast, screen, phone-TV, synthetic, and future sideline domains separate. Physical sideline is Coming later.

Maintain a manifest with recording permission/license, source hash, duration/PTS, resolution, camera profile, capture conditions, and annotation version. Include at least a short smoke set, a 90–120-minute soak recording, and a held-out accuracy set. Annotate players/ball/officials, stable identities, visible landmarks, event intervals, and explicitly unobservable periods. Double-review ambiguous events.

Annotation JSON accepted by `benchmark`:

```json
{
  "source_sha256": "ACTUAL_SHA256",
  "source_profile": "broadcast",
  "source_offset": 0,
  "frames": [
    {
      "time": 1.2,
      "sample_interval": 0.2,
      "objects": [{"id": "player-7", "kind": "person", "box": [0.1, 0.2, 0.15, 0.5]}]
    }
  ]
}
```

Boxes are normalized displayed-image coordinates after rotation. The CLI computes IoU≥0.5 precision/recall, sampled identity agreement/IDF1, switches, and switches per visible-player-minute. This is not AP over a confidence curve and not official HOTA; integrate TrackEval before publishing comparable tracking scores. `event_metrics` independently computes one-to-one same-class timestamp matching at a declared tolerance (default ±2 s); the current CLI does not yet run a trained event model.

## Release checks still required

1. **Accuracy:** Report per-class precision/recall and per-profile breakdowns, not one aggregate. Evaluate ball recall separately. Calibrate reliability bins on held-out data; abstain when evidence is insufficient. Promote no automatic event type until its precision gate and review burden are agreed and measured.
2. **Tracking:** Measure official HOTA/IDF1, switches, fragmentation, reacquisition after occlusion/cuts, and jersey/team confusion. Never interpolate long missing tracks into distance totals.
3. **Calibration:** Use held-out landmarks for reprojection error and known field distances for metric error. Test partial visibility, degenerate geometry, camera movement, and invalidation. Current manual fit error is not this validation.
4. **Live soak:** Run at least 120 minutes with actual phones/screens/streams. Measure capture PTS continuity, saved-video frame count, duplicates/drops, analysis skips, queue depth, RSS of all workers, disk growth, and p50/p95/p99 source-to-dashboard latency. The currently reported delay is saved-media-to-analysis lag, not sensor-to-screen latency.
5. **Fault injection:** Throttle/disconnect network, retry duplicate/out-of-order chunks, terminate workers, close server/browser, interrupt writes, fill a dedicated small test volume, truncate copies of recordings, and restart during deletion. Never fill the user's real disk to test failure.
6. **Corrections:** Add property-based tests for event/identity/calibration edits; incremental future recomputation must equal a clean rebuild. Verify split/link intervals, undo/redo branches, old-run corrections, source alignment, and pinned exports.
7. **Exports:** Decode every video/audio stream, verify duration and timestamps, compare annotated coordinates on landscape/portrait/non-square-pixel footage, confirm reel ordering and overlap merging, sanitize CSV/HTML, and check reports remain usable offline and in print.
8. **UI/device:** Real iOS Safari/Android Chrome HTTPS capture, macOS permissions, keyboard/accessibility audit, narrow displays, lengthy timelines, large libraries, and seek/playback through multiple segments. Desktop native Chrome has been manually inspected; device certification is not implied.

Release thresholds should be based on this corpus and agreed product promises. Do not silently substitute synthetic success for real-soccer performance.

## Provider comparison, September 29

[Raw measured matrix](../validation/provider-comparison-synthetic.json) uses one checksummed, locally generated 20-second 960×540 fixture, 100 samples at 5 fps, fresh processes, actual detector/tracker and ORT profiling. No third-party video was downloaded. These are synthetic engineering throughput measurements, not soccer accuracy or sensor-to-screen latency.

| Detector/provider | Sustained sampled frames/s | Init / first inference (s) | Peak worker RSS (MiB) | Runtime placement |
|---|---:|---:|---:|---|
| YOLOX Tiny CPU | 23.11 | 0.019 / 0.040 | 235.19 | CPU kernel trace |
| YOLOX Tiny CoreML | 69.41 | 0.427 / 2.463 | 257.52 | CoreML kernel trace |
| HOG CPU | 32.60 | 0.086 / 0.021 | 219.47 | OpenCV CPU |

CoreML raw outputs matched CPU on one decoded frame (`rtol=atol=0.001`, maximum absolute difference 0.00004297). This does not qualify full-corpus numerical parity, accuracy, or sustained live acceleration. CPU stays default. The initial sandboxed CoreML run failed to create a compilation directory; the reported matrix is the subsequent successful local run. Profiling adds overhead. YOLOX Small's raw-output adapter and matrix entries exist, but both small-model rows failed explicitly because no small weights were installed; this is not a completed neural-model comparison.

The CLI requires `--profile`, supports `--provider cpu|coreml`, and `--compare` uses isolated processes. Labels produce separate player, ball, small-ball, tracking and team-cluster metrics. Team metrics describe permutation-invariant color-cluster agreement and unknown coverage, not automatic named-team accuracy. A small model may be imported with `model import --variant small --file ...`; validate its license and raw-output contract before use.

Browser tests use actual Chrome MediaRecorder encoding of generated canvas streams, then authenticated chunks, receiver segmentation, TV alignment, and range playback. Physical getDisplayMedia permissions and iPhone camera behavior remain unverified. Annotation exchange includes checksum/profile/offset/revision, boxes/ball/team/identity, exclusions, events, TV reference/corners, and field landmarks; import is one reversible revision.

## Short recording/recovery soak

[Raw 180-second synthetic soak](../validation/soak-synthetic-180s.json) records in real time while a separate actual YOLOX CPU worker analyzes. An intentional analysis kill midway did not stop capture: 45 committed segments before the crash, 91 afterward, 181.355 seconds preserved. All video segments decoded, every segment contained generated audio, and segment timeline gaps were empty (0.1-second continuity tolerance). Measurements include worker/FFmpeg/decoder RSS, disk bytes, saved-media analysis delay and states. The harness had exposed an incorrect generated-audio input map; this artifact is the corrected rerun. No hardware compatibility, A/V sync accuracy, real-world frame-drop count, or 120-minute qualification is implied. Run `PYTHONPATH=src .venv/bin/python scripts/soak.py --seconds 7200 --model /path/to/yolox_tiny.onnx --output /path/to/result.json` for a longer generated engineering soak; the hardware gate is separate.
