#!/usr/bin/env python3
"""Turn keylog session files saved by monkeytype-keylogger.user.js into a
per-bigram latency table. Monkeytype's own API doesn't expose this; it only
gives test-level aggregates (see Typing Speed.md).

The userscript saves sessions into <Downloads>/monkeytype-keylogs/<date>/.
Move/clean those into data/keylogs/ here periodically, e.g.:
    mv ~/Downloads/monkeytype-keylogs/* data/keylogs/

Usage:
    python3 analyze_keylog.py                        # scans data/keylogs/**/*.json
    python3 analyze_keylog.py data/keylogs/2026-08-23/*.json
    python3 analyze_keylog.py some/other/file.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import TypedDict


class KeyEvent(TypedDict):
    ts: int
    key: str


DEFAULT_DIR = Path(__file__).parent.parent / "data" / "keylogs"
MAX_GAP_MS = 2000  # bigger gaps are a pause or a new test, not real bigram timing
MIN_SAMPLES = 5
TOP_N = 30


def resolve_paths(args: list[str]) -> list[Path]:
    if args:
        paths: list[Path] = []
        for a in args:
            p = Path(a)
            paths.extend(sorted(p.glob("**/*.json")) if p.is_dir() else [p])
        return paths
    if not DEFAULT_DIR.exists():
        sys.exit(
            f"No keylogs found under {DEFAULT_DIR}. Install "
            "monkeytype-keylogger.user.js, type on monkeytype.com, then run "
            "import_keylogs.py to pull sessions in from Downloads, or pass "
            "file paths directly."
        )
    return sorted(DEFAULT_DIR.glob("**/*.json"))


def load_events(paths: list[Path]) -> list[KeyEvent]:
    events: list[KeyEvent] = []
    for p in paths:
        with p.open() as f:
            payload = json.load(f)
        # accept either the {..., "events": [...]} envelope from
        # keylog_server.py or a bare array from an older manual export
        events.extend(payload["events"] if isinstance(payload, dict) else payload)
    return events


def bigram_latencies(events: list[KeyEvent]) -> dict[str, list[int]]:
    latencies: dict[str, list[int]] = defaultdict(list)
    prev: KeyEvent | None = None
    for e in sorted(events, key=lambda e: e["ts"]):
        key = e["key"]
        if len(key) == 1 and prev is not None and len(prev["key"]) == 1:
            gap = e["ts"] - prev["ts"]
            if 0 < gap <= MAX_GAP_MS:
                latencies[prev["key"] + key].append(gap)
        prev = e
    return latencies


def main() -> None:
    paths = resolve_paths(sys.argv[1:])
    events = load_events(paths)
    print(f"Loaded {len(events)} events from {len(paths)} file(s)")

    latencies = bigram_latencies(events)
    rows = [
        (bg, len(ts), median(ts), sum(ts) / len(ts))
        for bg, ts in latencies.items()
        if len(ts) >= MIN_SAMPLES
    ]
    rows.sort(key=lambda r: r[2], reverse=True)  # slowest median first

    print(f"{'bigram':<8}{'n':>6}{'median ms':>12}{'mean ms':>10}")
    for bg, n, med, mean in rows[:TOP_N]:
        print(f"{bg!r:<8}{n:>6}{med:>12.1f}{mean:>10.1f}")


if __name__ == "__main__":
    main()
