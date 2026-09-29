# Models and third-party components

MatchLens has no paid API or required cloud service. Free availability does not automatically settle every redistribution right; review exact dependency, model-weight, codec, and dataset terms before distributing a packaged application.

## Detector

- Official [YOLOX project](https://github.com/Megvii-BaseDetection/YOLOX), Apache-2.0 source code.
- [Official ONNX deployment reference](https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime).
- Official release artifact: `0.1.1rc0/yolox_tiny.onnx`, downloaded only on explicit model install.
- Pinned SHA-256: `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`.
- Local adapter: BGR float32, unnormalized 0–255 input, top-left letterbox 114, 416×416 for the pinned model, raw YOLOX grid decoding, person class 0 / sports-ball class 32, local NMS.
- COCO-pretrained model performance does not establish soccer, jersey, official-role, goal-structure, or video-game performance. No training corpus was bundled or downloaded in this implementation.
- The tracker is original project code inspired by two-stage association, not an import or validated reproduction of official ByteTrack. Re-identification and jersey OCR models are not bundled.

## Runtime and media

The main components are React, TypeScript, Vite, Lucide, FastAPI/Pydantic, Uvicorn, SQLite, NumPy/SciPy, OpenCV, ONNX Runtime, PyAV, FFmpeg, psutil, and filelock. Python versions tested here are recorded in `requirements-lock.txt`; frontend dependencies are locked by `package-lock.json`.

FFmpeg is invoked as an installed system executable, not bundled. Its build options and enabled codecs affect its licensing and codec obligations. The tested build uses libx264 for playback/export compatibility. Before shipping binaries, inspect [FFmpeg's legal/build notes](https://ffmpeg.org/legal.html) and the exact linked libraries. The [FFmpeg documentation](https://ffmpeg.org/ffmpeg.html) also defines display-rotation handling used by the portrait regression test.

MatchLens sets `ORT_DISABLE_TELEMETRY=1` at package initialization **before** importing ONNX Runtime, and also disables events through its API. The initialization-time environment flag is important: newer non-Windows official builds can initialize telemetry before the API disable call, as described in [ONNX Runtime's privacy documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md). The early development runs exposed that default through a local telemetry session artifact; it was removed and the startup opt-out was added before final verification. No game recording was sent to a cloud service by MatchLens, but network-level telemetry emission during those earlier runtime initializations was not audited.

MatchLens does not configure analytics, a model download during inference, external fonts, hosted scripts, or automatic sharing. Package installation and explicit model installation use the network; user-supplied remote stream URLs naturally contact their configured source.

## Second detector comparison

The official [0.1.1rc0 release](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0) metadata was inspected, and `yolox_s.onnx` was downloaded from its official GitHub release solely into temporary validation storage. Size: 35,858,002 bytes. SHA-256: `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`. Its source repository uses [Apache-2.0](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE); no weight is committed or redistributed by this checkout. Source/license URLs and hash identify the comparison artifact; they do not certify soccer accuracy. It uses the same raw-output adapter at its own 640×640 input shape. The original Tiny model stays available and CPU stays default. No third-party test video was downloaded.
