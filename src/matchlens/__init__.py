"""MatchLens: local media, explicit evidence, reversible review."""

__version__ = "0.1.0"
import os

# Must precede ONNX Runtime initialization, not just its later telemetry API call.
# MatchLens never opts users into runtime telemetry.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
