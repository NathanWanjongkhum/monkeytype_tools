#!/usr/bin/env python3
"""Rebuild typing.duckdb from the file sources (source of truth):
monkeytype_results.json and data/keylogs/**/*.json. See
docs/adr/0001-duckdb-derived-cache.md. This script can be rerun any time;
the DB is always dropped and reloaded from scratch.

Usage:
    python3 build_db.py
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import duckdb
import pandas as pd

import clilog
import db

HERE = Path(__file__).parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data"
RESULTS_JSON = DATA_DIR / "monkeytype_results.json"
TAGS_JSON = DATA_DIR / "monkeytype_tags.json"
KEYLOG_DIR = DATA_DIR / "keylogs"

# A coarse block boundary is a gap between consecutive keystrokes bigger
# than this. It's meant to catch "stepped away from the keyboard", not
# "started a new test". Checked the actual data: back-to-back tests
# (quick-restart) leave no detectable gap at all (next-biggest gap after a
# real 47s pause was 2.2s), so blocks routinely contain multiple tests.
# Per-test boundaries within a block come from slicing against each
# result's own recorded [est_start_ms, timestamp_ms] window instead (see
# segment_and_match).
SEGMENT_GAP_MS = 8_000

# How far a result's estimated time window may sit from a keystroke's
# timestamp and still claim that keystroke. Covers clock drift between the
# keylogger (client Date.now()) and the Monkeytype API server.
MATCH_TOLERANCE_MS = 3_000


# results


def load_results(con: duckdb.DuckDBPyConnection) -> None:
    if not RESULTS_JSON.exists():
        clilog.info("build_db", f"no {RESULTS_JSON.name}, skipping results load")
        return

    raw = json.loads(RESULTS_JSON.read_text())
    rows = []
    for r in raw:
        char_stats = r.get("charStats") or [None, None, None, None]
        test_duration = r.get("testDuration")
        # The API omits afkDuration/isPb entirely when they're the falsy
        # default (0 / false) rather than sending an explicit zero. Same
        # sparse-field convention as punctuation/numbers/tags elsewhere in
        # this API, confirmed against this account's 54 results (43/54 have
        # no afkDuration at all, none have a null testDuration).
        afk_duration = r.get("afkDuration") or 0
        is_pb = bool(r.get("isPb"))
        timestamp_ms = r.get("timestamp")
        est_start_ms = None
        if timestamp_ms is not None and test_duration is not None:
            est_start_ms = int(timestamp_ms - (test_duration + afk_duration) * 1000)

        rows.append(
            {
                "result_id": r["_id"],
                "uid": r.get("uid"),
                "wpm": r.get("wpm"),
                "raw_wpm": r.get("rawWpm"),
                "acc": r.get("acc"),
                "consistency": r.get("consistency"),
                "key_consistency": r.get("keyConsistency"),
                "mode": r.get("mode"),
                "mode2": r.get("mode2"),
                "language": r.get("language"),
                "difficulty": r.get("difficulty"),
                "quote_length": r.get("quoteLength"),
                "restart_count": r.get("restartCount"),
                "is_pb": is_pb,
                "punctuation": bool(r.get("punctuation")),
                "numbers": bool(r.get("numbers")),
                "incomplete_test_seconds": r.get("incompleteTestSeconds"),
                "test_duration": test_duration,
                "afk_duration": afk_duration,
                "chars_correct": char_stats[0],
                "chars_incorrect": char_stats[1],
                "chars_extra": char_stats[2],
                "chars_missed": char_stats[3],
                "tags": r.get("tags"),
                "timestamp_ms": timestamp_ms,
                "ts": pd.to_datetime(timestamp_ms, unit="ms") if timestamp_ms else None,
                "est_start_ms": est_start_ms,
            }
        )

    df = pd.DataFrame(rows)
    con.register("results_df", df)
    con.execute("INSERT INTO results SELECT * FROM results_df")
    con.unregister("results_df")
    clilog.info("build_db", f"loaded {len(df)} results")


def load_tags(con: duckdb.DuckDBPyConnection) -> None:
    if not TAGS_JSON.exists():
        clilog.info("build_db", f"no {TAGS_JSON.name}, skipping tags load")
        return

    raw = json.loads(TAGS_JSON.read_text())
    df = pd.DataFrame([{"tag_id": t["_id"], "name": t["name"]} for t in raw])
    con.register("tags_df", df)
    con.execute("INSERT INTO tags SELECT * FROM tags_df")
    con.unregister("tags_df")
    clilog.info("build_db", f"loaded {len(df)} tags")


# keylog sessions + events


def load_keylog(con: duckdb.DuckDBPyConnection) -> None:
    if not KEYLOG_DIR.exists():
        clilog.info("build_db", f"no {KEYLOG_DIR.name}/, skipping keylog load")
        return

    session_rows = []
    event_rows = []
    for f in sorted(KEYLOG_DIR.glob("**/*.json")):
        payload = json.loads(f.read_text())
        if isinstance(payload, list):
            # Older bare-array export with no envelope/config. Synthesize
            # a session id from the filename so it still gets a home.
            session_id = f.stem
            part = 1
            events = payload
            saved_at = None
            url = None
            config = None
            drill = None
        else:
            session_id = payload["session_id"]
            part = payload["part"]
            events = payload["events"]
            saved_at = payload.get("saved_at")
            url = payload.get("url")
            config = payload.get("config")
            drill = payload.get("drill")

        session_rows.append(
            {
                "session_id": session_id,
                "part": part,
                "url": url,
                "saved_at": pd.to_datetime(saved_at) if saved_at else None,
                "config": json.dumps(config) if config is not None else None,
                "drill": json.dumps(drill) if drill is not None else None,
                "source_file": str(f.relative_to(ROOT)),
            }
        )

        for seq, e in enumerate(events):
            event_rows.append(
                {
                    "session_id": session_id,
                    "part": part,
                    "seq": seq,
                    "ts_ms": e["ts"],
                    "key": e["key"],
                    "classes": e.get("classes", []),
                }
            )

    if session_rows:
        sdf = pd.DataFrame(session_rows)
        con.register("session_df", sdf)
        con.execute("INSERT INTO session_parts SELECT * FROM session_df")
        con.unregister("session_df")

    if event_rows:
        edf = pd.DataFrame(event_rows)
        edf["attempt_id"] = None
        con.register("event_df", edf)
        con.execute("INSERT INTO keylog_events SELECT * FROM event_df")
        con.unregister("event_df")
    clilog.info(
        "build_db", f"loaded {len(session_rows)} session files, {len(event_rows)} keylog events"
    )


# segmentation + matching: events -> attempts, sliced against result windows
#
# First pass: gap-based coarse blocks (a gap > SEGMENT_GAP_MS means the user
# stepped away, not just quick-restarted). This alone can't recover per-test
# boundaries though. Checked the actual data, and back-to-back tests here
# have zero gap over ~2.2s, well under any threshold that wouldn't also
# false-split mid-test thinking pauses. So within each coarse block, events
# get sliced against each overlapping result's own [est_start_ms,
# timestamp_ms] window instead: Monkeytype's own recorded test boundaries,
# not a guess from keystroke timing. Events outside every candidate window
# (before the first test, after the last, or with no candidate at all,
# i.e. custom/practice typing that never posted a result) become their own
# unmatched attempt rather than being dropped.


def _coarse_blocks(events: pd.DataFrame) -> Iterator[list[pd.Series]]:
    block: list[pd.Series] = []
    prev_ts = None
    for _, ev in events.iterrows():
        if prev_ts is not None and (ev["ts_ms"] - prev_ts) > SEGMENT_GAP_MS:
            yield block
            block = []
        block.append(ev)
        prev_ts = ev["ts_ms"]
    if block:
        yield block


def _assign_result(
    ts_ms: int, candidates: list[dict[str, Any]], pointer: list[int]
) -> dict[str, Any] | None:
    while (
        pointer[0] < len(candidates) - 1
        and ts_ms > candidates[pointer[0]]["timestamp_ms"] + MATCH_TOLERANCE_MS
    ):
        pointer[0] += 1
    c = candidates[pointer[0]] if candidates else None
    if (
        c
        and c["est_start_ms"] - MATCH_TOLERANCE_MS
        <= ts_ms
        <= c["timestamp_ms"] + MATCH_TOLERANCE_MS
    ):
        return c
    return None


_UNSET: Any = object()


def _runs(
    block: list[pd.Series], candidates: list[dict[str, Any]]
) -> Iterator[tuple[dict[str, Any] | None, list[pd.Series]]]:
    """Split a coarse block's events into consecutive runs that share the
    same assigned result (or share "no result"). Yields (result_or_None, events)."""
    pointer = [0]
    run_result: dict[str, Any] | None = _UNSET
    run_events: list[pd.Series] = []
    for ev in block:
        assigned = _assign_result(ev["ts_ms"], candidates, pointer)
        if run_result is not _UNSET and _key(assigned) != _key(run_result):
            yield run_result, run_events
            run_events = []
        run_events = [*run_events, ev]
        run_result = assigned
    if run_events:
        yield run_result, run_events


def _key(result: dict[str, Any] | None) -> str | None:
    return cast("str", result["result_id"]) if result else None


def segment_and_match(con: duckdb.DuckDBPyConnection) -> None:
    events = con.execute(
        "SELECT session_id, part, seq, ts_ms FROM keylog_events "
        "ORDER BY session_id, ts_ms, part, seq"
    ).fetchdf()
    results = (
        con.execute(
            "SELECT result_id, est_start_ms, timestamp_ms, "
            "chars_correct + chars_incorrect + chars_extra + chars_missed AS expected_chars "
            "FROM results WHERE est_start_ms IS NOT NULL ORDER BY est_start_ms"
        )
        .fetchdf()
        .to_dict("records")
    )

    attempt_rows = []
    event_assignments = []
    matched_count = 0
    attempt_count = 0

    for session_id, session_events in events.groupby("session_id", sort=False):
        for block_idx, block in enumerate(_coarse_blocks(session_events), start=1):
            start_ms, end_ms = block[0]["ts_ms"], block[-1]["ts_ms"]
            candidates = [
                r
                for r in results
                if r["timestamp_ms"] >= start_ms - MATCH_TOLERANCE_MS
                and r["est_start_ms"] <= end_ms + MATCH_TOLERANCE_MS
            ]

            for run_idx, (result, run_events) in enumerate(_runs(block, candidates), start=1):
                attempt_count += 1
                attempt_id = f"{session_id}#{block_idx}.{run_idx}"
                if result is None:
                    result_id, confidence, method = None, None, None
                else:
                    matched_count += 1
                    result_id = result["result_id"]
                    expected = result["expected_chars"]
                    confidence = min(1.0, len(run_events) / expected) if expected else 0.8
                    method = "sliced_by_result_window"
                attempt_rows.append(
                    {
                        "attempt_id": attempt_id,
                        "session_id": session_id,
                        "start_ms": run_events[0]["ts_ms"],
                        "end_ms": run_events[-1]["ts_ms"],
                        "event_count": len(run_events),
                        "result_id": result_id,
                        "match_confidence": confidence,
                        "match_method": method,
                    }
                )
                event_assignments.extend(
                    {
                        "session_id": ev["session_id"],
                        "part": ev["part"],
                        "seq": ev["seq"],
                        "attempt_id": attempt_id,
                    }
                    for ev in run_events
                )

    if attempt_rows:
        adf = pd.DataFrame(attempt_rows)
        con.register("attempt_df", adf)
        con.execute("INSERT INTO attempts SELECT * FROM attempt_df")
        con.unregister("attempt_df")

    if event_assignments:
        mdf = pd.DataFrame(event_assignments)
        con.register("assign_df", mdf)
        con.execute(
            "UPDATE keylog_events SET attempt_id = assign_df.attempt_id "
            "FROM assign_df "
            "WHERE keylog_events.session_id = assign_df.session_id "
            "AND keylog_events.part = assign_df.part "
            "AND keylog_events.seq = assign_df.seq"
        )
        con.unregister("assign_df")

    clilog.info("build_db", f"segmented {attempt_count} attempts, matched {matched_count}")


# phantom keystroke cleanup


def remove_phantom_double_spaces(con: duckdb.DuckDBPyConnection) -> None:
    """Delete the second keydown of any back-to-back-space pair within an
    Attempt. Two literal space characters in a row can never be real typed
    content in Monkeytype: space either ends a non-empty word or is a no-op
    on an already-empty one. So the first press is the legitimate
    word-ending space and the second is always a phantom the game state
    ignored. Cause (OS key-repeat while held vs. a fumbled double-tap) isn't
    knowable after the fact from timing alone (checked: gaps between same-key
    repeats form a smooth continuum from ~33ms up with no natural cutoff
    separating "repeat" from genuine fast double-letter typing), so this only
    targets the one case with actual proof, not a timing guess. Re-derived
    every rebuild per docs/adr/0001-duckdb-derived-cache.md: the raw
    keylog JSON is untouched, only this disposable DB drops the rows."""
    victims = con.execute("""
        SELECT session_id, part, seq FROM (
            SELECT session_id, part, seq, key,
                   LAG(key) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_key
            FROM keylog_events
        )
        WHERE key = ' ' AND prev_key = ' '
    """).fetchdf()
    if victims.empty:
        return
    con.register("victims_df", victims)
    con.execute("""
        DELETE FROM keylog_events
        USING victims_df
        WHERE keylog_events.session_id = victims_df.session_id
          AND keylog_events.part = victims_df.part
          AND keylog_events.seq = victims_df.seq
    """)
    con.unregister("victims_df")
    clilog.info("build_db", f"removed {len(victims)} phantom double-space keystrokes")


def main() -> None:
    con = db.connect()
    db.rebuild_schema(con)
    load_results(con)
    load_tags(con)
    load_keylog(con)
    segment_and_match(con)
    remove_phantom_double_spaces(con)
    con.close()
    clilog.ok("build_db", f"wrote {db.DB_PATH.name}")


if __name__ == "__main__":
    main()
