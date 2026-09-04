#!/usr/bin/env python3
"""Launch the Supervisor backend and UI together."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_SCRIPT = ROOT / "src" / "SupervisorAPI.py"
UI_DIR = ROOT / "UI"
UI_URL = "http://127.0.0.1:5173"
BACKEND_URL = "http://127.0.0.1:8000/api/health"


def find_python() -> str:
    candidates = []
    for venv_dir in (ROOT / ".venv", ROOT / "venv"):
        if os.name == "nt":
            candidates.append(venv_dir / "Scripts" / "python.exe")
        else:
            candidates.append(venv_dir / "bin" / "python")
    candidates.append(Path(sys.executable))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def ensure_ui_dependencies() -> None:
    if (UI_DIR / "node_modules").exists():
        return

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is not installed or not on PATH. Install Node.js to run the UI.")

    print("Installing frontend dependencies...")
    subprocess.run([npm, "install"], cwd=str(UI_DIR), check=True)


def wait_for_http(url: str, timeout_seconds: float, description: str) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"{description} did not become ready in time: {last_error}")


def start_backend() -> subprocess.Popen[str]:
    python_executable = find_python()
    print(f"Starting backend with: {python_executable} {BACKEND_SCRIPT}")
    return subprocess.Popen(
        [python_executable, str(BACKEND_SCRIPT)],
        cwd=str(ROOT),
        start_new_session=True,
    )


def start_ui() -> subprocess.Popen[str]:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is not installed or not on PATH. Install Node.js to run the UI.")

    print(f"Starting UI with: {npm} run dev -- --host 0.0.0.0")
    return subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "0.0.0.0"],
        cwd=str(UI_DIR),
        start_new_session=True,
    )


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return

    try:
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def main() -> int:
    ensure_ui_dependencies()
    backend_process = None
    ui_process = None

    try:
        backend_process = start_backend()
        wait_for_http(BACKEND_URL, 60, "Supervisor API")

        ui_process = start_ui()
        wait_for_http(UI_URL, 90, "UI")

        print("\nAll services are running.")
        print(f"Backend:  {BACKEND_URL}")
        print(f"UI:       {UI_URL}")
        print("Press Ctrl+C in this terminal to stop everything.")

        try:
            webbrowser.open(UI_URL)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not open browser automatically: {exc}")

        while True:
            if backend_process.poll() is not None:
                raise RuntimeError("Supervisor API exited unexpectedly.")
            if ui_process.poll() is not None:
                raise RuntimeError("UI exited unexpectedly.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    except Exception as exc:  # noqa: BLE001
        print(f"\nStartup failed: {exc}")
        return 1
    finally:
        stop_process(backend_process)
        stop_process(ui_process)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
