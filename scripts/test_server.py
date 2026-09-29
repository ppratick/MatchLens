"""Disposable HTTP server for Playwright. Never uses the user's library."""

import argparse
import tempfile

import uvicorn

from matchlens.api import create_app
from matchlens.config import Settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="matchlens-e2e-") as directory:
        uvicorn.run(create_app(Settings.load(directory)), host="127.0.0.1", port=args.port)
