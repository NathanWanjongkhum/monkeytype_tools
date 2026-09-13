#!/usr/bin/env python3
"""Pull all Monkeytype test results for the authenticated account and save
them locally as JSON + CSV, for the trend/tag-based analysis described in
Typing Speed.md.

Setup:
    pip install requests pandas
    Generate an ApeKey: Monkeytype > Settings > Danger Zone > Ape Keys
    export MONKEYTYPE_APE_KEY=apekey_xxx (or drop it in backend/.env - see
    envfile.load_env_file, which this script also uses so a key that only
    works through generate_dashboard.py doesn't silently fail when this is
    run standalone)

Usage:
    python fetch_monkeytype_results.py [output_dir]
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

import clilog
from envfile import load_env_file

API_BASE = "https://api.monkeytype.com"
PAGE_LIMIT = 1000
REQUEST_TIMEOUT_S = 30


def _raise_for_status_verbose(resp: requests.Response) -> None:
    """requests' own raise_for_status() only reports the status line - on
    a non-2xx, Monkeytype's API body carries the actual reason (bad/
    insufficiently-permissioned key, rate limit, etc.), so surface that
    too instead of leaving it to a bare traceback."""
    if resp.ok:
        return
    clilog.error("fetch", f"{resp.status_code} {resp.reason or ''} for {resp.url}: {resp.text}")
    resp.raise_for_status()


def fetch_all_results(ape_key: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"ApeKey {ape_key}"}
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API_BASE}/results",
            headers=headers,
            params={"limit": PAGE_LIMIT, "offset": offset},
            timeout=REQUEST_TIMEOUT_S,
        )
        _raise_for_status_verbose(resp)
        page = resp.json()["data"]
        if not page:
            break
        results.extend(page)
        if len(page) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(0.2)
    return results


def fetch_tags(ape_key: str) -> list[dict[str, Any]]:
    """Results only carry each tag as its opaque _id, never its name (see
    docs/adr/0003-drill-completion-validation.md) - this is the only call
    that returns the id -> name mapping needed to make sense of them."""
    headers = {"Authorization": f"ApeKey {ape_key}"}
    resp = requests.get(f"{API_BASE}/users/tags", headers=headers)
    _raise_for_status_verbose(resp)
    return resp.json()["data"]


def main() -> None:
    load_env_file()
    ape_key = os.environ.get("MONKEYTYPE_APE_KEY")
    if not ape_key:
        sys.exit("Set MONKEYTYPE_APE_KEY (Monkeytype > Settings > Danger Zone > Ape Keys)")

    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = fetch_all_results(ape_key)

    json_path = out_dir / "monkeytype_results.json"
    with json_path.open("w") as f:
        json.dump(results, f, indent=2)
    clilog.ok("fetch", f"{len(results)} results -> {json_path}")

    tags = fetch_tags(ape_key)
    tags_path = os.path.join(out_dir, "monkeytype_tags.json")
    with open(tags_path, "w") as f:
        json.dump(tags, f, indent=2)
    clilog.ok("fetch", f"{len(tags)} tags -> {tags_path}")

    try:
        import pandas as pd  # noqa: PLC0415 -- optional dependency, probed at runtime
    except ImportError:
        clilog.warn("fetch", "pandas not installed, skipping CSV export")
        return

    df = pd.json_normalize(results)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values("timestamp")
    csv_path = out_dir / "monkeytype_results.csv"
    df.to_csv(csv_path, index=False)
    clilog.info("fetch", f"wrote {csv_path}")


if __name__ == "__main__":
    main()
