"""Tiny, dependency-free .env loader shared by refresh.py and
fetch_monkeytype_results.py. Split out on its own so a script that only
needs MONKEYTYPE_APE_KEY (fetch_monkeytype_results.py) doesn't have to
import refresh.py and, transitively, build_db.py's duckdb/pandas
dependency just to read a key out of a text file.
"""
import os
from pathlib import Path

HERE = Path(__file__).parent


def load_env_file():
    """Populate os.environ from backend/.env (MONKEYTYPE_APE_KEY=...) if
    it's not already set, so a bare `export` or running standalone both
    work with no extra setup."""
    env_path = HERE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            # Tolerate a line copy-pasted straight from a shell `export
            # KEY=val` command - this script's own docstring shows that
            # exact form as the alternative to a .env file, and without
            # this the "export " prefix becomes part of the key name, so
            # MONKEYTYPE_APE_KEY itself never actually gets set.
            key = key[len("export "):].strip()
        val = val.strip().strip("'").strip('"')
        os.environ.setdefault(key, val)
