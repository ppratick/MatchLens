"""Fresh process for each detector/provider experiment; no UI or capture coupling."""

import sys
import traceback
from pathlib import Path

from .config import Settings
from .evaluation import benchmark_video
from .storage import atomic_json

if __name__ == "__main__":
    directory, video, output, fps, detector, provider, profile, *labels = sys.argv[1:]
    try:
        result = benchmark_video(
            Settings.load(directory),
            Path(video),
            float(fps),
            detector,
            labels[0] if labels else None,
            provider=provider,
            profile=profile,
        )
        result["status"] = "measured"
    except Exception as exc:
        traceback.print_exc()
        result = {"detector": detector, "provider": provider, "status": "failed", "error": str(exc)}
    atomic_json(Path(output), result)
