"""Disposable, loopback-only campus for the browser acceptance suite."""

import os
import sys
import tempfile
from pathlib import Path
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import create_app

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="omnis-e2e-") as folder:
        uvicorn.run(
            create_app("sqlite:///" + (Path(folder) / "browser.db").as_posix(), True),
            host="127.0.0.1",
            port=8127,
            log_level="warning",
        )
