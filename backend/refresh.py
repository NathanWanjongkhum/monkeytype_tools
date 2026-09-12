"""Refresh pipeline: pull fresh Monkeytype results + import keylogs, and
rebuild typing.duckdb, but only actually rebuild the database when the
source files it's built from have changed. build_db.main() is a full
drop-and-reload (docs/adr/0001-duckdb-derived-cache.md), which is cheap
today but is "the expensive step" this module exists to gate: fetching
results and scanning for new keylogs happens every call (that's what makes
the dashboard feel fresh on every open), the DB rebuild only happens when
there's actually something new to fold in.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

import build_db
import clilog
from envfile import load_env_file

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
STATE_PATH = DATA_DIR / ".refresh_state.json"
RESULTS_JSON = DATA_DIR / "monkeytype_results.json"
KEYLOG_DIR = DATA_DIR / "keylogs"


class _MainModule(Protocol):
    """Structural type for a script module invoked as `module.main()`."""

    def main(self) -> None: ...


def call_with_argv(source: str, module: _MainModule, argv: list[str]) -> None:
    """Call module.main() with a temporary sys.argv. Catches both its
    intentional sys.exit() error paths and any unexpected exception (bad
    API key -> HTTPError, no network -> ConnectionError, etc.). This step
    is explicitly best-effort, so any failure here degrades to "rebuild
    from whatever's already local" rather than crashing the whole run."""
    old_argv = sys.argv
    try:
        sys.argv = argv
        module.main()
    except (SystemExit, Exception) as e:  # noqa: BLE001 -- deliberately best-effort, see docstring
        clilog.warn(source, f"skipped: {e}")
    finally:
        sys.argv = old_argv


def refresh_results() -> None:
    load_env_file()
    if not os.environ.get("MONKEYTYPE_APE_KEY"):
        clilog.info("fetch", "MONKEYTYPE_APE_KEY not set, using local data only")
        return
    import fetch_monkeytype_results  # noqa: PLC0415 -- deferred: only needed on this path

    call_with_argv(
        "fetch", fetch_monkeytype_results, ["fetch_monkeytype_results.py", str(DATA_DIR)]
    )


def refresh_keylogs() -> None:
    import import_keylogs  # noqa: PLC0415 -- deferred: only needed on this path

    call_with_argv("keylogs", import_keylogs, ["import_keylogs.py"])


def _results_fingerprint() -> dict[str, Any] | None:
    """(count, last result id) instead of monkeytype_results.json's mtime.
    fetch_monkeytype_results.py rewrites that file on every run regardless
    of whether the content actually changed, so its mtime alone would defeat
    the gate below and trigger a rebuild on every single dashboard open."""
    if not RESULTS_JSON.exists():
        return None
    try:
        data = json.loads(RESULTS_JSON.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not data:
        return {"count": 0, "last_id": None}
    return {"count": len(data), "last_id": data[-1].get("_id")}


def _source_fingerprint() -> dict[str, Any]:
    """Cheap stand-in for "did anything build_db.py reads from actually
    change since last time". Keylog files, unlike monkeytype_results.json,
    are only ever written once by import_keylogs.py and never rewritten, so
    mtime-of-newest-file is a reliable signal for them."""
    keylog_mtime = None
    keylog_count = 0
    if KEYLOG_DIR.exists():
        for f in KEYLOG_DIR.glob("**/*.json"):
            keylog_count += 1
            m = f.stat().st_mtime
            if keylog_mtime is None or m > keylog_mtime:
                keylog_mtime = m
    return {
        "results": _results_fingerprint(),
        "keylog_mtime": keylog_mtime,
        "keylog_count": keylog_count,
    }


def _load_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_state(fingerprint: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(fingerprint))


def rebuild_if_changed() -> bool:
    """Rebuild typing.duckdb only if the source files changed since the last
    rebuild (by either this function or rebuild_forced). Returns whether a
    rebuild happened."""
    fingerprint = _source_fingerprint()
    if fingerprint == _load_state():
        return False
    build_db.main()
    _save_state(fingerprint)
    return True


def rebuild_forced() -> None:
    """Unconditional rebuild, the explicit/manual path (generate_dashboard.py
    as a CLI launcher), as opposed to rebuild_if_changed's implicit gate."""
    build_db.main()
    _save_state(_source_fingerprint())
