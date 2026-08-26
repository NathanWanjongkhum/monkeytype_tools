#!/usr/bin/env python3
"""One-command entry point for the typing dashboard: refreshes results +
keylogs, force-rebuilds typing.duckdb, makes sure server.py (:8000) and the
Vite dev server (:5173) are up, and opens the browser. Frontend edits then
hot-reload through Vite with no rerun needed - see docs on the refresh gate
in refresh.py for why opening the dashboard itself also stays fresh.

Usage:
    python3 generate_dashboard.py             # refresh + open
    python3 generate_dashboard.py --no-open   # refresh, skip the browser
    python3 generate_dashboard.py --offline   # rebuild from local data only
"""
import argparse
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import clilog
import refresh

HERE = Path(__file__).parent
API_PORT = 8000
VITE_PORT = 5173
LOG_DIR = HERE / ".dashboard_logs"

SERVICES = {
    "server": {
        "port": API_PORT,
        "cmd": [sys.executable, "-m", "uvicorn", "server:app", "--port", str(API_PORT)],
        "cwd": HERE,
    },
    "vite": {
        "port": VITE_PORT,
        "cmd": ["npm", "run", "dev", "--", "--port", str(VITE_PORT)],
        "cwd": HERE.parent / "frontend",
    },
}


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


def _stream(name: str, proc: subprocess.Popen, log_file) -> None:
    """Relay a supervised subprocess's output live, tagged and colored by
    source, while also keeping the raw log file for post-mortems."""
    for line in proc.stdout:
        log_file.write(line)
        line = line.rstrip("\n")
        if line:
            print(f"{clilog.tag(name)} {line}")
    log_file.close()


def start_service(name: str) -> subprocess.Popen | None:
    """Start a service if its port is free. Returns the Popen handle if we
    started it (and are therefore responsible for it), None if it was
    already running (someone else owns it)."""
    spec = SERVICES[name]
    if _port_open(spec["port"]):
        clilog.info(name, f"already running on :{spec['port']}")
        return None

    LOG_DIR.mkdir(exist_ok=True)
    log_file = open(LOG_DIR / f"{name}.log", "w")
    proc = subprocess.Popen(
        spec["cmd"], cwd=spec["cwd"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    threading.Thread(target=_stream, args=(name, proc, log_file), daemon=True).start()

    if not _wait_for_port(spec["port"]):
        clilog.warn(name, f"still not up on :{spec['port']} after 20s, see {LOG_DIR}/{name}.log")
    return proc


def watch(owned: dict[str, subprocess.Popen]) -> None:
    """Block for as long as the services we started stay up. If one exits
    early, say so and keep watching whatever's left. Ctrl+C shuts the rest
    down cleanly."""
    if not owned:
        return
    clilog.info("dashboard", "watching " + ", ".join(owned) + " (Ctrl+C to stop)")
    alive = dict(owned)
    try:
        while alive:
            for name, proc in list(alive.items()):
                code = proc.poll()
                if code is None:
                    continue
                del alive[name]
                log = clilog.ok if code == 0 else clilog.error
                log(name, f"exited (code {code})" + (f", {', '.join(alive)} still up" if alive else ""))
            if alive:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        for name, proc in alive.items():
            clilog.info(name, "stopping")
            proc.terminate()
        for proc in alive.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-open", action="store_true", help="don't launch a browser")
    ap.add_argument("--offline", action="store_true", help="rebuild from local data only")
    args = ap.parse_args()

    if not args.offline:
        refresh.refresh_results()
        refresh.refresh_keylogs()
    refresh.rebuild_forced()

    owned = {name: proc for name in SERVICES if (proc := start_service(name)) is not None}

    url = f"http://localhost:{VITE_PORT}"
    clilog.ok("dashboard", url)
    if not args.no_open:
        webbrowser.open(url)

    watch(owned)


if __name__ == "__main__":
    main()
