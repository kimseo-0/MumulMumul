from __future__ import annotations
import subprocess
import sys
import time
from typing import Optional


def _spawn_process(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd)


def main() -> int:
    python = sys.executable

    streamlit_cmd = [
        python,
        "-m",
        "streamlit",
        "run",
        "streamlit_app/main.py",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]

    print("Starting uvicorn and streamlit...")
    streamlit_proc: Optional[subprocess.Popen] = None

    try:
        streamlit_proc = _spawn_process(streamlit_cmd)

        print(f"streamlit PID: {streamlit_proc.pid}")

        # Wait until one of them exits or we get KeyboardInterrupt
        while True:
            if streamlit_proc.poll() is not None:
                print("streamlit exited")
                break
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("Interrupted. Stopping processes...")

    return 0


if __name__ == "__main__":
    print("Hello from mumulmumul!")
    raise SystemExit(main())