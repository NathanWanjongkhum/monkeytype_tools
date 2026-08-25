"""Schema + connection for typing.duckdb, the derived cache described in
docs/adr/0001-duckdb-derived-cache.md.

This file is disposable and fully rebuilt by build_db.py from the JSON/CSV
sources (monkeytype_results.json, data/keylogs/**/*.json), which remain the
source of truth. Deleting typing.duckdb and rerunning build_db.py is always
safe.
"""
from pathlib import Path

import duckdb

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
DB_PATH = DATA_DIR / "typing.duckdb"

SCHEMA = """
CREATE TABLE results (
    result_id               VARCHAR PRIMARY KEY,
    uid                     VARCHAR,
    wpm                     DOUBLE,
    raw_wpm                 DOUBLE,
    acc                     DOUBLE,
    consistency             DOUBLE,
    key_consistency         DOUBLE,
    mode                    VARCHAR,
    mode2                   VARCHAR,
    language                VARCHAR,
    difficulty              VARCHAR,
    quote_length            BIGINT,
    restart_count           BIGINT,
    is_pb                   BOOLEAN,
    incomplete_test_seconds DOUBLE,
    test_duration           DOUBLE,
    afk_duration            DOUBLE,
    chars_correct           BIGINT,
    chars_incorrect         BIGINT,
    chars_extra             BIGINT,
    chars_missed            BIGINT,
    tags                    VARCHAR[],
    timestamp_ms            BIGINT,
    ts                      TIMESTAMP,
    est_start_ms            BIGINT
);

CREATE TABLE session_parts (
    session_id  VARCHAR,
    part        INTEGER,
    url         VARCHAR,
    saved_at    TIMESTAMP,
    config      JSON,
    source_file VARCHAR,
    PRIMARY KEY (session_id, part)
);

CREATE TABLE keylog_events (
    session_id VARCHAR,
    part       INTEGER,
    seq        INTEGER,
    ts_ms      BIGINT,
    key        VARCHAR,
    classes    VARCHAR[],
    attempt_id VARCHAR
);

CREATE TABLE attempts (
    attempt_id       VARCHAR PRIMARY KEY,
    session_id       VARCHAR,
    start_ms         BIGINT,
    end_ms           BIGINT,
    event_count      INTEGER,
    result_id        VARCHAR,
    match_confidence DOUBLE,
    match_method     VARCHAR
);
"""


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def rebuild_schema(con: duckdb.DuckDBPyConnection) -> None:
    for table in ("attempts", "keylog_events", "session_parts", "results"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(SCHEMA)
