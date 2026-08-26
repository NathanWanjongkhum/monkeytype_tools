"""Tiny colored, source-tagged console output shared by the dashboard CLI
(generate_dashboard.py) and the modules it drives in-process (refresh.py,
fetch_monkeytype_results.py, import_keylogs.py, build_db.py). Subprocesses we
supervise (server.py via uvicorn, the Vite dev server) get their tag applied
line-by-line by the supervisor itself instead, since we don't control their
raw output - see generate_dashboard.py's _stream().
"""
import os
import sys

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

_RESET = "\033[0m"
TAG_COLORS = {
    "dashboard": "36",  # cyan
    "fetch": "34",  # blue
    "keylogs": "33",  # yellow
    "build_db": "94",  # bright blue
    "server": "35",  # magenta
    "vite": "32",  # green
}


def _wrap(code: str, s: str) -> str:
    return f"\033[{code}m{s}{_RESET}" if COLOR else s


def tag(source: str) -> str:
    return _wrap(TAG_COLORS.get(source, "37"), f"[{source}]")


def info(source: str, msg: str) -> None:
    print(f"{tag(source)} {msg}")


def ok(source: str, msg: str) -> None:
    print(f"{tag(source)} {_wrap('32', msg)}")


def warn(source: str, msg: str) -> None:
    print(f"{tag(source)} {_wrap('33', msg)}")


def error(source: str, msg: str) -> None:
    print(f"{tag(source)} {_wrap('31;1', msg)}", file=sys.stderr)
