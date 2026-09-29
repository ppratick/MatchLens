"""Disposable HTTP servers for Playwright. Never uses the user's library."""

import argparse
import tempfile
import threading

import uvicorn

from matchlens.api import create_app
from matchlens.config import Settings
from matchlens.jobs import Supervisor
from matchlens.phone import receiver_app
from matchlens.storage import Store

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="matchlens-e2e-") as directory:
        settings = Settings.load(directory)
        app = create_app(settings)
        receiver = uvicorn.Server(
            uvicorn.Config(receiver_app(settings), host="127.0.0.1", port=args.port + 1, log_level="warning")
        )
        thread = threading.Thread(target=receiver.run, daemon=True)
        thread.start()
        try:
            uvicorn.run(app, host="127.0.0.1", port=args.port)
        finally:
            receiver.should_exit = True
            thread.join(timeout=3)
            store = Store(settings)
            supervisor = Supervisor(store)
            for match in store.list():
                supervisor.stop_match(match["id"])
