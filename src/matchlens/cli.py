from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .config import Settings
from .storage import atomic_json

MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"
MODEL_SHA256 = "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"


def install_model(settings, source=None, variant="tiny"):
    from filelock import FileLock

    settings.initialize()
    with FileLock(str(settings.data_dir / "models/install.lock"), timeout=120):
        return _install_model(settings, source, variant)


def _install_model(settings, source=None, variant="tiny"):
    if variant == "small" and not source:
        raise ValueError(
            "Import a locally licensed raw-output YOLOX small ONNX export with --file; automatic small-model download is not configured"
        )
    settings.initialize()
    target = settings.data_dir / ("models/yolox_s.onnx" if variant == "small" else "models/yolox_tiny.onnx")
    staged = target.with_suffix(".download")
    try:
        if source:
            shutil.copyfile(Path(source).expanduser(), staged)
        else:
            print("Downloading the official YOLOX tiny ONNX model (~20 MB). Inference stays local.")
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response, staged.open("wb") as out:
                shutil.copyfileobj(response, out)
        from .media import sha256

        checksum = sha256(staged)
        if not source and checksum != MODEL_SHA256:
            raise ValueError("Upstream model checksum changed. Review the release before installing it.")
        import numpy as np

        from .vision import YOLOX

        model = YOLOX(staged)
        model.detect(np.zeros((416, 416, 3), dtype=np.uint8))
        staged.replace(target)
        atomic_json(
            target.with_suffix(".json"),
            {
                "name": "yolox-small" if variant == "small" else "yolox-tiny",
                "source": str(source) if source else MODEL_URL,
                "sha256": checksum,
                "code_license": "Apache-2.0",
                "weight_terms": "Review upstream release terms before redistribution",
                "input": "BGR float32 0..255, top-left letterbox 114",
                "output": "raw YOLOX grid",
                "soccer_accuracy": "unvalidated",
            },
        )
        print(f"Installed {target}\nSHA-256: {checksum}")
    finally:
        staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="MatchLens local sports video analysis")
    parser.add_argument("--data-dir", help="Nonsynced local storage directory")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start the local interface")
    serve.add_argument("--port", type=int, default=8765)
    model = sub.add_parser("model", help="Install or import local model")
    model.add_argument("action", choices=["install", "import"])
    model.add_argument("--file")
    model.add_argument("--variant", choices=["tiny", "small"], default="tiny")
    sub.add_parser("doctor", help="Inspect dependencies and local capabilities")
    sub.add_parser("devices", help="List macOS capture devices; may trigger OS permission prompts")
    receiver = sub.add_parser(
        "receiver", help="Run optional LAN phone receiver, separated from local application API"
    )
    receiver.add_argument("--host", default="0.0.0.0")
    receiver.add_argument("--port", type=int, default=8766)
    receiver.add_argument("--cert", required=True)
    receiver.add_argument("--key", required=True)
    benchmark = sub.add_parser("benchmark", help="Evaluate an installed detector against a local video")
    benchmark.add_argument("video")
    benchmark.add_argument("--fps", type=float, default=5)
    benchmark.add_argument("--output", required=True)
    benchmark.add_argument("--annotations", help="Optional MatchLens evaluation JSON")
    benchmark.add_argument("--detector", choices=["yolox", "yolox_s", "hog"], default="yolox")
    benchmark.add_argument("--provider", choices=["cpu", "coreml"], default="cpu")
    benchmark.add_argument(
        "--profile", choices=["broadcast", "screen", "phone_tv", "synthetic", "sideline"], required=True
    )
    benchmark.add_argument(
        "--compare", action="store_true", help="Fresh-process comparison of tiny/small/HOG and CPU/CoreML"
    )
    args = parser.parse_args()
    settings = Settings.load(args.data_dir)
    if args.command == "serve":
        import uvicorn

        from .api import create_app

        print(f"MatchLens: http://127.0.0.1:{args.port}\nLocal data: {settings.data_dir}")
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)
    elif args.command == "model":
        if args.action == "import" and not args.file:
            parser.error("model import requires --file")
        install_model(settings, args.file, args.variant)
    elif args.command == "doctor":
        import platform

        import onnxruntime

        print(
            json.dumps(
                {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "ffmpeg": shutil.which(settings.ffmpeg),
                    "ffprobe": shutil.which(settings.ffprobe),
                    "data_dir": str(settings.data_dir),
                    "model_ready": (settings.data_dir / "models/yolox_tiny.onnx").exists(),
                    "providers": onnxruntime.get_available_providers(),
                },
                indent=2,
            )
        )
    elif args.command == "devices":
        subprocess.run(
            [settings.ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
        )
    elif args.command == "receiver":
        import uvicorn

        from .phone import receiver_app

        uvicorn.run(
            receiver_app(settings),
            host=args.host,
            port=args.port,
            ssl_certfile=args.cert,
            ssl_keyfile=args.key,
            access_log=False,
        )
    elif args.command == "benchmark":
        from .evaluation import benchmark_video

        if args.compare:
            from .evaluation import compare_providers

            result = compare_providers(settings, Path(args.video), args.fps, args.annotations, args.profile)
        else:
            result = benchmark_video(
                settings,
                Path(args.video),
                args.fps,
                args.detector,
                args.annotations,
                provider=args.provider,
                profile=args.profile,
            )
        atomic_json(Path(args.output), result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
