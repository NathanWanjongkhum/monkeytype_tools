#!/usr/bin/env python3
"""The single entry point for the typing dashboard: pulls fresh Monkeytype
results, imports any new keylog sessions sitting in Downloads, force-rebuilds
typing.duckdb, makes sure the API server (server.py) and the Vite dev server
(frontend/) are running, and opens the dashboard in a browser, so running
this script is the whole workflow, same as before. Once both servers are up,
editing the frontend (frontend/src/) hot-reloads through Vite directly. This
script doesn't need to be rerun for that, only to force a fresh pull of
results/keylogs. Opening the dashboard itself also refreshes (see server.py's
GET /api/dashboard), this script's rebuild is the explicit/unconditional
version of that same gate (see refresh.py).

Usage:
    python3 generate_dashboard.py             # refresh everything + open it
    python3 generate_dashboard.py --no-open   # refresh + ensure servers, skip the browser
    python3 generate_dashboard.py --offline   # skip the API/Downloads refresh, rebuild from local data only
"""
import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import refresh

HERE = Path(__file__).parent
API_PORT = 8000
VITE_PORT = 5173
LOG_DIR = HERE / ".dashboard_logs"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: float = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(port):
            return True
        time.sleep(0.3)
    return False


def ensure_server_running():
    if _port_open(API_PORT):
        print(f"[dashboard] API server already running on :{API_PORT}")
        return
    LOG_DIR.mkdir(exist_ok=True)
    log = open(LOG_DIR / "server.log", "w")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--port", str(API_PORT)],
        cwd=HERE,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    if not _wait_for_port(API_PORT):
        print(f"[dashboard] warning: API server didn't come up on :{API_PORT} in time, "
              f"see {LOG_DIR / 'server.log'}")


def ensure_vite_running():
    if _port_open(VITE_PORT):
        print(f"[dashboard] Vite dev server already running on :{VITE_PORT}")
        return
    LOG_DIR.mkdir(exist_ok=True)
    log = open(LOG_DIR / "vite.log", "w")
    subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(VITE_PORT)],
        cwd=HERE.parent / "frontend",
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    if not _wait_for_port(VITE_PORT):
        print(f"[dashboard] warning: Vite dev server didn't come up on :{VITE_PORT} in time, "
              f"see {LOG_DIR / 'vite.log'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true", help="don't launch a browser")
    ap.add_argument(
        "--offline",
        action="store_true",
        help="skip the API/Downloads refresh, rebuild from local data only",
    )
    args = ap.parse_args()

    if not args.offline:
        refresh.refresh_results()
        refresh.refresh_keylogs()
    refresh.rebuild_forced()

    ensure_server_running()
    ensure_vite_running()

    url = f"http://localhost:{VITE_PORT}"
    print(f"[dashboard] {url}")
    if not args.no_open:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
