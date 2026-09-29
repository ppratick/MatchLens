# Operations and recovery

## Daily use

Start `.venv/bin/python run.py serve`, then open `http://127.0.0.1:8765`. No login is required. The application is intended for a trusted local user, not a shared multi-tenant server. The local session token protects browser-origin writes; it does not protect against malicious software already running as your OS user.

Before a real match, test your exact camera, cable/network, permissions, and available disk space with a short recording. Preview a saved segment and listen to its audio. Keep the computer awake and connected to power. The 512 MiB free-space reserve is an emergency stop threshold, not enough planned space for a whole match. Storage usage depends on the input and chosen encoding; budget generously and measure a representative recording.

Stopping the UI server does not stop independent workers. Reopen the server to see their status and use **Stop recording**. Analysis can be paused/resumed. Clip/report jobs run to completion; they are not resumable. Export work waits while recording is active.

## Phone HTTPS receiver

The receiver is optional and must be explicitly started. Its camera page requires a secure context, a certificate trusted by the phone, and camera/microphone permission. Do not bypass browser security warnings. Configure local certificate trust deliberately on your own device.

1. Put the phone and computer on a trusted local network that permits device-to-device traffic.
2. Obtain a locally trusted TLS certificate whose SAN includes the computer's LAN hostname or IP. A local development CA tool or your existing certificate tooling can do this without a paid service. Certificate generation/trust installation is not automated by MatchLens.
3. Start `.venv/bin/python run.py receiver --cert /path/to/cert.pem --key /path/to/key.pem`. Use `--host COMPUTER-LAN-IP` to bind a specific interface instead of all interfaces.
4. In the match, choose **Capture → Phone on your network**. Open the displayed URL, replacing `COMPUTER-IP` with the actual host covered by your certificate. The fragment contains a temporary secret; do not share it.
5. Grant camera/microphone access on the phone. Start the camera in landscape, mark all four TV corners clockwise, save alignment, then start recording. Keep the page foregrounded and verify committed saved segments appear on the computer; chunk receipts alone do not establish playable recording. Press **Finish recording** and wait for all chunks to drain before closing the page.

Pairings expire after four hours. Only the secret hash is persisted in pairing metadata. The receiver accepts ordered chunks with retry acknowledgment and durable committed byte offsets. It cannot browse/export/delete matches. The application API stays on localhost:8765.

The browser buffer is bounded; a full buffer pauses capture, producing missing real-world time. This transport does not promise continuous capture when the phone locks, backgrounds the tab, loses power, or changes networks. Original received bytes are retained separately from normalized segments. Physical iOS/Android interoperability has not been tested in this environment; the automated test uses an actual WebM stream split into authenticated HTTP chunks.

Do not expose the receiver through internet port forwarding. Stop it when not in use. A leaked pairing URL should be treated as compromised; stop its recording and create a new pairing. Restarting the UI rotates its local session token but does not revoke phone pairings.

## Recovery semantics

| Failure | What is retained | Recovery |
|---|---|---|
| Analysis exception/kill | Copied original and all committed analysis batches | Resume the failed/paused job; last incomplete batch is replayed |
| UI closed / sender closed | Workers and committed files remain; browser sender input ends | Reopen UI; finalize/drain sender before closing; use a new pairing after sender reload |
| UI server restarted | Independent workers and job records | Supervisor checks PID creation time and reconnects |
| Stream ends/disconnects | Previously closed segments and received phone bytes | Inspect the gap; reconnect as another source and set its explicit timeline offset before analysis |
| Recorder killed/power loss | Previously committed segments | Unclosed MP4 tail may be unreadable; no lossless recovery claim |
| Disk reserve reached | Earlier committed segments | Free space outside active originals; reconnect/restart explicitly |
| Corrupt import | User's external original untouched | Repair a copy externally and reimport; do not overwrite evidence |
| Interrupted deletion | Managed folder in `deleting/` | Next Store startup finishes cleanup |
| Export failure | Original and review state | Retry as a new export; inspect per-job logs |

Live skipped analysis is not a recording drop. It is recorded in job checkpoint/metrics. Run a new offline analysis after the source is finalized. Actual device/network dropped-frame counting is not yet comprehensive; a zero-drop guarantee is not made.

Analysis resumes only with matching pipeline/model/source provenance. If these changed, start a new run. Selecting an earlier run restores its observations, but corrections are tied to the original track IDs, not automatically transferred to new identities.

## Troubleshooting

- **No local model:** run `run.py model install` once, or import the supported ONNX file offline. HOG can exercise the pipeline but is not a quality substitute for sports training.
- **Video will not play:** wait for the queued browser proxy. The original stays separate. Captures expose only committed segments, so the first preview has a short delay.
- **Capture has no frames:** verify the AVFoundation device index, OS permission, URL, and source format. The job/FFmpeg logs are under the match's `logs/` directory.
- **Slow analysis:** reduce sampling from 5 to 2 fps. Do not lower recording quality solely to hide an inference bottleneck. Check stage benchmarks before modifying the model/runtime.
- **Poor field projection:** use spread-out known landmarks, choose a stationary view, and recalibrate after movement. Do not project an airborne ball with ground homography. Four-point fit error is not independent calibration accuracy.
- **Unexpected statistic:** inspect the confirmed timeline, exclusions, identity intervals, active run, unknown possession, and revision. Rejected/proposed events do not count as confirmed results.
- **Stale edit rejected:** reload the latest match revision rather than silently overwriting someone else's edit.
- **Another server is running:** use its existing localhost address; do not remove its lock to run a second scheduler.

## Backups and deletion

For a consistent manual backup, stop capture/analysis, stop the server, and copy the entire data directory (including SQLite WAL files if still present) to storage you control. MatchLens does not enable OS backups or sharing automatically.

**Delete match** stops its owned workers, removes the match's managed recordings, proxies, tracks, review database, reports, logs, and pairing metadata, and removes the library entry. External originals, downloaded exports, browser downloads, system backups, and other copies are outside its ownership and remain. Shared model weights are retained for other matches.

Deletion is logical filesystem deletion, not a claim of forensic erasure from SSDs, APFS snapshots, or backups. SQLite secure-delete is enabled and match deletion requests a library WAL checkpoint/truncation. Use OS disk encryption and your backup/retention controls if forensic confidentiality is required. No sharing or remote deletion service is implemented.

## Screen, television, and version selection

**Capture → Choose display or window** invokes the browser's visible picker. A denied or cancelled request does not imply OS permission was granted. Follow the displayed System Settings instructions yourself. No system setting is changed automatically. Audio is captured only if the selected stream actually supplies an audio track. Protected broadcasts may be blank. Keep the sender tab open; the UI server and recording worker remain separate from inference.

TV rectification uses original-image corners and an immutable reference frame. Movement checking matches static surroundings outside the television; too few features produce an explicit unavailable warning, not a claim of stable alignment. Detected movement latches invalidation and withholds detection; obscuration withholds uncertain samples. Re-mark corners and create a new analysis run after movement. Glare, blur, low-light, and orientation hints are heuristics; flicker, rolling bands, moiré, extreme viewing angle, and audio synchronization still need device validation.

Each sender session uses a fresh epoch. Network retries reuse the same chunk sequence and bytes. Reload/restart needs a new pairing/source, so separate timelines are never silently joined. Buffer pauses and suspension create identified interruptions with unknown exact media boundaries. Clips across unknown-boundary source gaps are conservatively rejected. Previous committed media and received bytes remain available. The buffer has a 24 MiB pause threshold, with possible overshoot by a final browser-emitted blob; it is not a hard allocation ceiling.

Offline/live runs stay separate. Open **Source alignment & analysis versions** and explicitly choose the new completed offline version. Existing identity corrections remain attached to their original track IDs.
