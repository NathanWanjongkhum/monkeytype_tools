# DuckDB as a derived cache over file-based sources

We have two growing data sources (Monkeytype Results as JSON/CSV, keylogger Events as per-Session JSON files) that need to be joined and queried together over months/years of history. We chose **DuckDB** (a single embedded `.duckdb` file, no DuckLake) over SQLite or a server database, since the workload is entirely analytical reads/joins/aggregates with a single writer, and DuckDB's pandas/numpy interop fits the existing analysis code directly.

The DuckDB file is a **derived, disposable cache**, not the source of truth: `fetch_monkeytype_results.py` and `import_keylogs.py` keep writing the JSON/CSV files as before, and a separate load step (re)builds the DuckDB tables from those files. It can be deleted and rebuilt at any time with no data loss — deliberate, since Attempt-matching (segmenting keylog Events and matching them to Results) is expected to be iterated on, and we didn't want schema/logic changes to require a migration.

Keylog Events are stored at raw per-keystroke grain (not pre-aggregated bigram stats), and unmatched Attempts are kept with a nullable `result_id` plus `match_confidence`/`match_method`, rather than discarded — captured keystrokes are irreplaceable even when the matching logic isn't.
