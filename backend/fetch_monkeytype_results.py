#!/usr/bin/env python3
"""Pull all Monkeytype test results for the authenticated account and save
them locally as JSON + CSV, for the trend/tag-based analysis described in
Typing Speed.md.

Setup:
    pip install requests pandas
    Generate an ApeKey: Monkeytype > Settings > Danger Zone > Ape Keys
    export MONKEYTYPE_APE_KEY=apekey_xxx

Usage:
    python fetch_monkeytype_results.py [output_dir]
"""
import json
import os
import sys
import time

import requests

import clilog

API_BASE = "https://api.monkeytype.com"
PAGE_LIMIT = 1000


def fetch_all_results(ape_key: str) -> list[dict]:
    headers = {"Authorization": f"ApeKey {ape_key}"}
    results = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API_BASE}/results",
            headers=headers,
            params={"limit": PAGE_LIMIT, "offset": offset},
        )
        resp.raise_for_status()
        page = resp.json()["data"]
        if not page:
            break
        results.extend(page)
        if len(page) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(0.2)
    return results


def main():
    ape_key = os.environ.get("MONKEYTYPE_APE_KEY")
    if not ape_key:
        sys.exit(
            "Set MONKEYTYPE_APE_KEY (Monkeytype > Settings > Danger Zone > Ape Keys)"
        )

    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)

    results = fetch_all_results(ape_key)

    json_path = os.path.join(out_dir, "monkeytype_results.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    clilog.ok("fetch", f"{len(results)} results -> {json_path}")

    try:
        import pandas as pd
    except ImportError:
        clilog.warn("fetch", "pandas not installed, skipping CSV export")
        return

    df = pd.json_normalize(results)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values("timestamp")
    csv_path = os.path.join(out_dir, "monkeytype_results.csv")
    df.to_csv(csv_path, index=False)
    clilog.info("fetch", f"wrote {csv_path}")


if __name__ == "__main__":
    main()
