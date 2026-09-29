from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    min_free_bytes: int = 512 * 1024 * 1024

    @classmethod
    def load(cls, data_dir: str | Path | None = None):
        if data_dir is None:
            default = (
                Path.home() / "Library/Application Support/MatchLens"
                if sys.platform == "darwin"
                else Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "MatchLens"
            )
            data_dir = os.environ.get("MATCHLENS_DATA_DIR", str(default))
        return cls(
            Path(data_dir).expanduser().resolve(),
            shutil.which("ffmpeg") or "ffmpeg",
            shutil.which("ffprobe") or "ffprobe",
        )

    def initialize(self):
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("matches", "models", "temporary", "deleting"):
            (self.data_dir / name).mkdir(exist_ok=True, mode=0o700)

    def match_dir(self, match_id: str) -> Path:
        import re

        if not re.fullmatch(r"[a-f0-9]{32}", match_id):
            raise ValueError("Invalid match ID")
        return self.data_dir / "matches" / match_id

    def require_space(self, extra: int = 0):
        if shutil.disk_usage(self.data_dir).free < self.min_free_bytes + extra:
            raise ValueError("Insufficient free space. Recording reserve is 512 MiB.")
