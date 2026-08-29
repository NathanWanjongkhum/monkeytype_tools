#!/usr/bin/env python3
"""Local API for the Vue dashboard (frontend/). The only piece that talks to
typing.duckdb. GET /api/dashboard mtime-gates a refresh (see refresh.py) so
opening the dashboard always reflects current data without redoing the
DuckDB rebuild when nothing actually changed.

Usage:
    uvicorn server:app --port 8000 --reload
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

import dashboard_data as dd
import db as typing_db
import generate_drill_list
import refresh

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _sanitize(obj):
    """Make DuckDB/pandas/numpy output JSON-safe: NaN/NaT -> None, numpy
    scalars -> native Python, Timestamps -> ISO strings, sets -> lists."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (pd.Timestamp,)):
        return None if pd.isna(obj) else obj.isoformat()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if obj is pd.NaT:
        return None
    return obj


def _build_payload() -> dict:
    con = typing_db.connect()
    try:
        df = dd.load_results_db(con)
        if df.empty:
            raise HTTPException(
                status_code=503,
                detail="No results in typing.duckdb and none could be fetched. "
                "Set MONKEYTYPE_APE_KEY (env var or .env) and try again.",
            )

        bigram_rows, keylog_events, keylog_sessions = dd.load_bigram_rows_db(con)
        freq_by_key, latency_by_key = dd.load_key_stats_db(con)
        drill_validation = dd.compute_drill_validation(con)
    finally:
        con.close()

    has_tags = df["tags"].notna().any() if "tags" in df.columns else False

    kpis = dd.compute_kpis(df)
    insights = dd.compute_insights(df, bigram_rows)
    actions = dd.compute_action_plan(kpis, insights, has_tags)
    popular_tests_rows = dd.compute_popular_tests(df)
    (
        ergo_overall_avg,
        ergo_overall_median,
        ergo_overall_representative,
        ergo_category_rows,
        ergo_detail_rows,
    ) = dd.compute_bigram_ergonomics(bigram_rows)

    drill_text = generate_drill_list.generate(bigram_rows)
    category_drills = generate_drill_list.generate_category_drills(bigram_rows)

    series = (
        df[
            ["timestamp", "wpm", "acc", "mode", "mode2", "is_pb", "language", "punctuation",
             "numbers", "raw_wpm", "testDuration"]
        ]
        .rename(columns={"testDuration": "test_duration"})
        .to_dict("records")
    )

    drills = {
        "overall": {"text": drill_text, "path": "drill_practice.txt" if drill_text else None},
        "categories": [
            {
                "key": d["key"],
                "label": d["label"],
                "desc": d["desc"],
                "n_entries": len(d["entries"]),
                "text": d["text"],
                "path": d.get("path"),
            }
            for d in category_drills
        ],
    }

    payload = {
        "kpis": kpis,
        "insights": {k: v for k, v in insights.items() if k != "bigram_rows"},
        "has_tags": has_tags,
        "actions": actions,
        "bigram_rows": bigram_rows,
        "popular_tests": popular_tests_rows,
        "ergonomics": {
            "overall_avg": ergo_overall_avg,
            "overall_median": ergo_overall_median,
            "overall_representative": ergo_overall_representative,
            "category_rows": ergo_category_rows,
            "detail_rows": ergo_detail_rows,
        },
        "drills": drills,
        "drill_validation": drill_validation,
        "series": series,
        "key_stats": {"freq": freq_by_key, "latency": latency_by_key},
        "keylog_events": keylog_events,
        "keylog_sessions": keylog_sessions,
    }
    return _sanitize(payload)


@app.get("/api/dashboard")
def get_dashboard():
    refresh.refresh_results()
    refresh.refresh_keylogs()
    rebuilt = refresh.rebuild_if_changed()
    if rebuilt:
        print("db rebuilt")
    return _build_payload()


@app.get("/drills/{name}")
def get_drill_file(name: str):
    path = (DATA_DIR / name).resolve()
    if path.parent != DATA_DIR.resolve() or not path.name.startswith("drill_practice"):
        raise HTTPException(status_code=404)
    if not path.exists():
        raise HTTPException(status_code=404)
    return PlainTextResponse(path.read_text())


def _read_drill_manifest(txt_name: str):
    """Reads a drill_practice*.json sidecar (written by
    generate_drill_list.write_manifest) plus its matching .txt, without
    touching the DB - see docs/adr/0003-drill-completion-validation.md for
    why the userscript needs this instead of re-deriving bigrams from
    whatever the dashboard is currently regenerating."""
    txt_path = (DATA_DIR / txt_name).resolve()
    json_path = txt_path.with_suffix(".json")
    if txt_path.parent != DATA_DIR.resolve() or not json_path.exists():
        return None
    manifest = json.loads(json_path.read_text())
    manifest["text"] = txt_path.read_text() if txt_path.exists() else None
    return manifest


@app.get("/api/drill-manifest")
def get_drill_manifest():
    """Lightweight (no DB access) companion to /drills/{name}: tells the
    keylogger userscript which bigrams and category are behind the most
    recently generated drill, so it can auto-fill Monkeytype's custom text
    and apply the matching completion tag."""
    return {
        "overall": _read_drill_manifest("drill_practice.txt"),
        "categories": [
            m for key, _, _ in dd.BIGRAM_CATEGORIES
            if (m := _read_drill_manifest(f"drill_practice_{key}.txt")) is not None
        ],
    }
