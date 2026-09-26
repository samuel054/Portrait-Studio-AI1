"""Start the local API and website after dependency installation."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    node = shutil.which("node")
    next_cli = ROOT / "frontend/node_modules/next/dist/bin/next"
    if not node or not next_cli.is_file():
        raise SystemExit("Install Node.js, then run: npm --prefix frontend ci")
    env = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
    env.update(os.environ)
    env.setdefault("PORTRAIT_ENABLE_BACKGROUND_WORKER", "true")
    processes = []
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
                env=env,
            )
        )
        processes.append(
            subprocess.Popen(
                [node, str(next_cli), "dev", "--hostname", "127.0.0.1", "--port", "3000"],
                cwd=ROOT / "frontend",
                env=env,
            )
        )
        print(
            "Portrait Studio AI: http://127.0.0.1:3000\nKeep this terminal open. Ctrl+C stops both services.",
            flush=True,
        )
        while all(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
