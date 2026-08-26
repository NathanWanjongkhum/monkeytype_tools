#!/usr/bin/env python3
"""Move keylog session files monkeytype-keylogger.user.js saved into
Downloads into this project's data/keylogs/, keeping the date-partitioned
layout analyze_keylog.py expects.

Usage:
    python3 import_keylogs.py
    python3 import_keylogs.py --source ~/Downloads/monkeytype-keylogs --dest data/keylogs
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import clilog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source", default=str(Path.home() / "Downloads" / "monkeytype-keylogs")
    )
    ap.add_argument(
        "--dest", default=str(Path(__file__).parent.parent / "data" / "keylogs")
    )
    args = ap.parse_args()

    source = Path(args.source)
    dest = Path(args.dest)

    if not source.exists():
        sys.exit(f"No source folder at {source} - nothing to import yet")

    files = sorted(source.glob("**/*.json"))
    if not files:
        clilog.info("keylogs", f"nothing new under {source}")
        return

    moved, skipped = 0, 0
    for f in files:
        try:
            with open(f) as fh:
                json.load(fh)
        except (json.JSONDecodeError, OSError):
            clilog.warn("keylogs", f"skip (unreadable, maybe still being written): {f.name}")
            skipped += 1
            continue

        rel = f.relative_to(source)  # e.g. 2026-08-23/<session>-part1.json
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            skipped += 1
            continue

        shutil.move(str(f), str(target))
        moved += 1

    if moved or skipped:
        clilog.ok("keylogs", f"imported {moved}, skipped {skipped} -> {dest}")

    # clean up now-empty date subfolders left behind in source
    for d in sorted(source.glob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


if __name__ == "__main__":
    main()
