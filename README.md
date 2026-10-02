# MatchLens

A local-first soccer video review application. Import a recording, track observed players, review a timestamped timeline, map positions to a field, correct the analysis, and export clips and reports. No account, paid API, subscription, or cloud processing is required.

**Release status: 0.1 engineering beta, not a fully autonomous soccer analyst.** The application and local processing workflow are implemented. Real-match detection/tracking accuracy is unvalidated; automatic goals, shots, passes, turnovers, and saves are not implemented as reliable classifiers. These events can be entered, corrected, and confirmed manually. Experimental ball-control proposals must be reviewed. See [actual capabilities and validation](docs/STATUS.md), not just the longer-term [project plan](PLAN.md).

## Run an installed checkout

Complete the fresh installation below first. From the repository directory:

```sh
.venv/bin/python run.py serve
```

Open **http://127.0.0.1:8765**. If the server is already running, just open the address. In the library, import a video or explore the explicitly labeled synthetic demonstration.

Recordings and analysis default to:

```text
~/Library/Application Support/MatchLens
```

This is deliberately outside the iCloud-backed code checkout. Changing `MATCHLENS_DATA_DIR` or using `run.py --data-dir /absolute/path serve` changes the storage location; choose a nonsynced local directory.

## Fresh installation

Requires Python 3.12+, Node.js 22+, and FFmpeg/FFprobe on PATH. This checkout was tested on Python 3.14.7, Node 22.13.1, FFmpeg 9.0.2, macOS 27.0.1, Apple M2 Pro, 16 GB RAM. Other platforms are not certified. Screen selection uses the desktop browser picker; indexed device capture also supports macOS AVFoundation.

```sh
git clone https://github.com/ppratick/MatchLens.git
cd MatchLens
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
npm ci
npm run build
.venv/bin/python run.py doctor
.venv/bin/python run.py model install
.venv/bin/python run.py serve
```

Installation downloads dependencies and the ~20 MB model. Normal analysis does not download anything. Import offline weights from **Local setup**, or use `run.py model import --file /path/to/yolox_tiny.onnx`. Small raw-output weights use `--variant small` and can be selected separately in Analyze match. Imported custom weights must use the supported YOLOX raw-output contract; they are shape-tested, not authenticated as official weights. The official download is SHA-256 pinned.

The source launcher explicitly adds `src` to Python's path. This avoids relying on editable `.pth` files in environments that mark hidden-directory contents with filesystem hidden flags.

## First match

1. Create a match and import an MP4/MOV/MKV/WebM or other FFmpeg-readable video. Import copies the original; analysis never overwrites it. Unsupported browser codecs queue a separate playback proxy.
2. Choose **Analyze match**, YOLOX, and 5 sampled frames/second. This is analysis sampling, not recording frame rate. HOG is a limited fallback; the synthetic detector is restricted to synthetic matches.
3. Inspect the video and player tracks. Assign reviewed teams/names/roles. Model color clusters are suggestions, not named teams. Track IDs do not prove persistent player identity.
4. For a stationary full-pitch view, calibrate four known corners; for partial views, enable paired landmarks and mark at least four known image/field correspondences. Set the verified stationary validity interval (one second by default). Camera cuts invalidate previous calibration. Distance and speed are deliberately withheld.
5. Add/review events. Only confirmed, nonexcluded timeline events contribute to score and counts. Confirming a goal, shot, or save queues a surrounding clip. Unknown possession, including contested time, remains in the denominator.
6. Export a custom clip, annotated clip, team/player reel, or self-contained HTML report with JSON/CSV. Print the HTML report to PDF if needed. Export manifests retain the review revision; later corrections do not silently change old exports.

Keyboard shortcuts in the studio: Space play/pause, Left/Right seek 5 seconds, E add event. Escape closes dialogs.

## Capture and phone streaming

Use **Capture → Choose display or window** for the browser source picker. Permission denial produces manual macOS instructions. Audio availability is reported from the actual selected stream; keep the recording tab open. An explicit stream URL, indexed AVFoundation input, and synthetic capture remain available. `run.py devices` lists AVFoundation indexes and may prompt for macOS permissions. Device index `0:none` does not necessarily mean your screen—check the list. Grant camera/screen/microphone permission yourself when appropriate.

The optional phone receiver is a separate HTTPS service on the local network, not an exposed administration API. Pair from a match, run the receiver with a trusted certificate, and open the pairing URL on the phone. See [operations](docs/OPERATIONS.md) for setup and limitations. No receiver is started automatically.

Recording uses independently committed media segments. Live analysis processes saved segments, with bounded memory and visible analysis delay. When overloaded, analysis reduces sampling, hides expensive overlays, skips stale work with recorded analysis gaps, then enters recording-only mode if necessary. Recorded media is preserved. Run a new offline analysis after recording to recover analysis coverage. Buffered playback is not a zero-latency camera monitor.

## Development and verification

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
npm run typecheck
npm run build
npm run format:check
```

For separate frontend development, run the backend and `npm run dev`; Vite proxies the local API and media. No external fonts, CDNs, or analytics are used.

For HTTP verification, start an isolated instance using `run.py --data-dir /private/tmp/matchlens-check serve --port 8875`, then run `.venv/bin/python scripts/verify_local.py --url http://127.0.0.1:8875`. The script refuses libraries outside temporary directories. Browser workflows use `npm run test:e2e` with their own disposable servers and generated camera/screen streams; they do not certify OS permissions or physical phones.

```sh
.venv/bin/python run.py benchmark /path/to/video.mp4 --fps 5 --profile broadcast --compare --output /path/to/result.json
```

Supply `--annotations /path/to/labels.json` to compute sampled-frame accuracy against checksum-matched labels. Without labels, the result explicitly says accuracy was not evaluated. See [evaluation](docs/EVALUATION.md).

## Design and safety

- [Architecture and interfaces](docs/ARCHITECTURE.md)
- [Operations, recovery, phone setup, and deletion](docs/OPERATIONS.md)
- [Implemented / partial / not implemented](docs/STATUS.md)
- [Testing and release gates](docs/EVALUATION.md)
- [Dependency and model notes](docs/THIRD_PARTY.md)

Stop recordings in the app before shutting down the computer. Stopping the UI server does **not** kill recording workers. Closing a screen or phone sender page ends its input; wait for sender finalization before closing it. Original media cannot be guaranteed against disk failure, power loss, full disks, or a disconnected source; previous committed segments are preserved. Keep a separate backup when recordings matter.

## Review and validation

Use **Label frame** to draw player boxes or ball positions, label visible teams/identities, and mark camera cuts, replays, closeups, non-play, contested, or unknown intervals. Export/import uses a strict schema, original checksum, source profile, timeline offset, and review revision. Television corners and field landmarks travel with the labels. Edits support undo/redo. TV setup preserves the original video; start a new analysis run to apply rectification. A later offline run requires explicit version selection before replacing the selected live run.

CPU remains the default. CoreML is configurable and experimental; short synthetic placement/parity/throughput measurements are documented in [evaluation](docs/EVALUATION.md). No real soccer accuracy or iPhone compatibility has been established. Physical sideline recording is **Coming later**. See the [completion roadmap and hardware procedures](docs/COMPLETION_ROADMAP.md).
