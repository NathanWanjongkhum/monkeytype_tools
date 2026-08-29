"""Pure compute/query layer for the typing dashboard: DuckDB loaders and the
stats/insights computed from them. No HTML/SVG/JS; server.py serves this as
JSON and frontend/ renders it. Split out of what used to be
generate_dashboard.py so the compute layer has no presentation code mixed
into it.
"""
import json
import math

import numpy as np

MAX_GAP_MS = 2000
MIN_SAMPLES = 5
RECENT_N = 10

# Standard QWERTY touch-typing chart: hand, finger rank (1=index..4=pinky),
# row (0=top, 1=home, 2=bottom). Each index finger covers two columns: its
# home column (r/f/v, u/j/m) and a "stretch" column reached toward the
# keyboard's center (t/g/b, y/h/n). The stretch column is flagged separately
# below for the lateral-stretch check.
FINGER_MAP = {
    "q": ("L", 4, 0),
    "w": ("L", 3, 0),
    "e": ("L", 2, 0),
    "r": ("L", 1, 0),
    "t": ("L", 1, 0),
    "a": ("L", 4, 1),
    "s": ("L", 3, 1),
    "d": ("L", 2, 1),
    "f": ("L", 1, 1),
    "g": ("L", 1, 1),
    "z": ("L", 4, 2),
    "x": ("L", 3, 2),
    "c": ("L", 2, 2),
    "v": ("L", 1, 2),
    "b": ("L", 1, 2),
    "y": ("R", 1, 0),
    "u": ("R", 1, 0),
    "i": ("R", 2, 0),
    "o": ("R", 3, 0),
    "p": ("R", 4, 0),
    "h": ("R", 1, 1),
    "j": ("R", 1, 1),
    "k": ("R", 2, 1),
    "l": ("R", 3, 1),
    ";": ("R", 4, 1),
    "n": ("R", 1, 2),
    "m": ("R", 1, 2),
    ",": ("R", 2, 2),
    ".": ("R", 3, 2),
    "/": ("R", 4, 2),
}
STRETCH_KEYS = {"t", "g", "b", "y", "h", "n"}

# Physical QWERTY layout, used only to build CHAR_TO_KEY below (the frontend
# owns its own copy for drawing the heatmap grid).
KEYBOARD_ROWS = [
    [("`", "~"), ("1", "!"), ("2", "@"), ("3", "#"), ("4", "$"), ("5", "%"),
     ("6", "^"), ("7", "&"), ("8", "*"), ("9", "("), ("0", ")"), ("-", "_"), ("=", "+")],
    [("q", None), ("w", None), ("e", None), ("r", None), ("t", None), ("y", None),
     ("u", None), ("i", None), ("o", None), ("p", None), ("[", "{"), ("]", "}"), ("\\", "|")],
    [("a", None), ("s", None), ("d", None), ("f", None), ("g", None), ("h", None),
     ("j", None), ("k", None), ("l", None), (";", ":"), ("'", '"')],
    [("z", None), ("x", None), ("c", None), ("v", None), ("b", None), ("n", None),
     ("m", None), (",", "<"), (".", ">"), ("/", "?")],
]
SPACE_KEY = " "


def _build_char_to_key():
    mapping = {SPACE_KEY: SPACE_KEY}
    for row in KEYBOARD_ROWS:
        for base, shifted in row:
            mapping[base] = base
            if base.isalpha():
                mapping[base.upper()] = base
            if shifted:
                mapping[shifted] = base
    return mapping


CHAR_TO_KEY = _build_char_to_key()

BIGRAM_CATEGORIES = [
    (
        "sfb",
        "Same-finger bigrams (SFB)",
        "Same finger presses two different keys back to back.",
    ),
    (
        "row_skip",
        "Row-skipping bigrams",
        "Same finger jumps two rows or more, e.g. top row to bottom row.",
    ),
    (
        "awkward_roll",
        "Outward and descending rolls",
        "Same-hand sequence moves toward the pinky, or drops a row, against the hand's natural inward curl.",
    ),
    (
        "lsb",
        "Lateral-stretch bigrams (LSB)",
        "Index finger reaches into its stretch column (t/g/b or y/h/n) while another finger on that hand holds position.",
    ),
]

# Monkeytype's standard presets, shown in this fixed order regardless of
# whether any tests exist yet for a given one. Rows with n=0 still render
# (as an explicit "no tests yet" row) rather than being omitted, so the
# breakdown always covers the same fixed set of test types.
POPULAR_TESTS = [
    ("time", "15"),
    ("time", "30"),
    ("time", "60"),
    ("time", "120"),
    ("words", "10"),
    ("words", "25"),
    ("words", "50"),
    ("words", "100"),
    ("quote", None),
]


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------


def load_results_db(con):
    df = con.execute(
        "SELECT ts AS timestamp, wpm, acc, consistency, mode, mode2, "
        "test_duration AS testDuration, raw_wpm, restart_count, "
        "chars_incorrect + chars_extra + chars_missed AS error_count, tags, "
        "is_pb, language, punctuation, numbers "
        "FROM results WHERE ts IS NOT NULL ORDER BY ts"
    ).fetchdf()
    return df.reset_index(drop=True)


def load_bigram_rows_db(con):
    """Bigram latency, sourced from typing.duckdb instead of rescanning
    data/keylogs/ directly. Pairs are taken within an Attempt, not a whole
    Session, because a Session can chain several tests back-to-back with no
    detectable gap (checked: as little as ~0ms between them), so pairing
    across a session would wrongly treat "last key of test N" + "first key
    of test N+1" as a real bigram. attempt_id already carries that boundary.

    Only pulls events from Attempts matched to a real Monkeytype result
    (attempts.result_id IS NOT NULL). An unmatched Attempt is keystrokes the
    segmenter couldn't tie to any submitted test - old keylogger versions
    logged these unconditionally whenever #wordsInput wasn't found (settings,
    profile, leaderboard search, ...), so they're not trustworthy test
    typing: confirmed against this data, ~25% of attempts were unmatched,
    averaging ~34 events vs. ~414 for matched ones, and unmatched attempts
    are exactly where bigrams that never occur in real test content (e.g.
    "==", "atm") were coming from. See docs/adr/0001-duckdb-derived-cache.md
    for why unmatched Attempts are kept in the DB rather than discarded -
    they still need excluding here, at the point stats get computed."""
    rows = con.execute(f"""
        WITH matched_events AS (
            SELECT ke.attempt_id, ke.ts_ms, ke.key
            FROM keylog_events ke
            JOIN attempts a ON a.attempt_id = ke.attempt_id
            WHERE a.result_id IS NOT NULL
        ),
        ordered AS (
            SELECT attempt_id, ts_ms, key,
                   LAG(key) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_key,
                   LAG(ts_ms) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_ts
            FROM matched_events
        ),
        pairs AS (
            SELECT prev_key || key AS bigram, ts_ms - prev_ts AS gap
            FROM ordered
            WHERE length(key) = 1 AND length(prev_key) = 1
              AND ts_ms - prev_ts > 0 AND ts_ms - prev_ts <= {MAX_GAP_MS}
        )
        SELECT bigram, count(*) AS n, median(gap) AS median, avg(gap) AS mean
        FROM pairs
        GROUP BY bigram
        HAVING count(*) >= {MIN_SAMPLES}
        ORDER BY median DESC
    """).fetchdf().to_dict("records")

    n_events = con.execute("""
        SELECT count(*) FROM keylog_events ke
        JOIN attempts a ON a.attempt_id = ke.attempt_id
        WHERE a.result_id IS NOT NULL
    """).fetchone()[0]
    n_sessions = con.execute(
        "SELECT count(DISTINCT session_id) FROM session_parts"
    ).fetchone()[0]
    return rows, n_events, n_sessions


def load_bigram_pairs_db(con):
    """Same attempt-scoped LAG pairing as load_bigram_rows_db, but one row
    per keystroke pair (bigram, ts_ms, gap) instead of aggregated medians -
    compute_drill_validation needs to slice by time window relative to a
    specific tagged completion, not the whole history at once."""
    return con.execute(f"""
        WITH matched_events AS (
            SELECT ke.attempt_id, ke.ts_ms, ke.key
            FROM keylog_events ke
            JOIN attempts a ON a.attempt_id = ke.attempt_id
            WHERE a.result_id IS NOT NULL
        ),
        ordered AS (
            SELECT attempt_id, ts_ms, key,
                   LAG(key) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_key,
                   LAG(ts_ms) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_ts
            FROM matched_events
        )
        SELECT prev_key || key AS bigram, ts_ms, ts_ms - prev_ts AS gap
        FROM ordered
        WHERE length(key) = 1 AND length(prev_key) = 1
          AND ts_ms - prev_ts > 0 AND ts_ms - prev_ts <= {MAX_GAP_MS}
    """).fetchdf()


def load_tagged_drill_completions_db(con):
    """Genuine drill completions: a matched Attempt whose Result carries the
    `drill-<category>` tag that the keylogger userscript applies after a
    completed custom-mode drill test, joined back to the session_parts.drill
    manifest recorded when that drill was loaded (docs/adr/
    0003-drill-completion-validation.md - the tag alone only proves *a*
    drill of that category happened, not which bigrams; the manifest is
    the only record of that, since the drill files themselves regenerate
    from live data on every dashboard load). Only completions where the tag
    actually matches the manifest's own category are trusted - a stale tag
    from a since-changed drill, or a hand-applied tag with no matching
    session, is dropped rather than guessed at."""
    rows = con.execute("""
        SELECT a.attempt_id, a.end_ms, r.tags, any_value(sp.drill) AS drill
        FROM attempts a
        JOIN results r ON r.result_id = a.result_id
        JOIN keylog_events ke ON ke.attempt_id = a.attempt_id
        JOIN session_parts sp ON sp.session_id = ke.session_id AND sp.part = ke.part
        WHERE a.result_id IS NOT NULL AND sp.drill IS NOT NULL AND r.tags IS NOT NULL
        GROUP BY a.attempt_id, a.end_ms, r.tags
    """).fetchdf().to_dict("records")

    completions = []
    for r in rows:
        manifest = json.loads(r["drill"]) if isinstance(r["drill"], str) else r["drill"]
        if not manifest or not manifest.get("category") or not manifest.get("bigrams"):
            continue
        tags = list(r["tags"]) if r["tags"] is not None else []
        expected_tag = f"drill-{manifest['category']}"
        if expected_tag not in tags:
            continue
        completions.append({
            "attempt_id": r["attempt_id"],
            "end_ms": r["end_ms"],
            "category": manifest["category"],
            "bigrams": manifest["bigrams"],
        })
    return completions


def compute_drill_validation(con):
    """For every genuine (tagged) drill completion, compares each targeted
    bigram's keystroke latency from before that completion to after it -
    the passive validation signal from docs/adr/0003-drill-completion-
    validation.md. The category tag only locates completions; the bigram
    (not category) is the unit of comparison, since there's no fixed "the
    SFB bigrams" once drills regenerate from live data on every request. A
    bigram recurring across multiple tagged completions produces one
    before/after instance per occurrence, rolled up here by averaging.
    Requires MIN_SAMPLES on both sides of a given occurrence to count it,
    same noise floor as everywhere else bigram latency gets computed."""
    completions = load_tagged_drill_completions_db(con)
    if not completions:
        return []
    pairs = load_bigram_pairs_db(con)
    if pairs.empty:
        return []

    occurrences_by_bigram = {}
    for c in completions:
        t = c["end_ms"]
        for bigram in c["bigrams"]:
            sub = pairs[pairs["bigram"] == bigram]
            before = sub.loc[sub["ts_ms"] < t, "gap"]
            after = sub.loc[sub["ts_ms"] > t, "gap"]
            if len(before) < MIN_SAMPLES or len(after) < MIN_SAMPLES:
                continue
            before_median, after_median = before.median(), after.median()
            occurrences_by_bigram.setdefault(bigram, []).append({
                "category": c["category"],
                "before_median": before_median,
                "after_median": after_median,
                "delta_ms": before_median - after_median,
            })

    report = []
    for bigram, occurrences in occurrences_by_bigram.items():
        report.append({
            "bigram": bigram,
            "category": occurrences[-1]["category"],  # most recent completion's category
            "occurrences": len(occurrences),
            "avg_before_median": sum(o["before_median"] for o in occurrences) / len(occurrences),
            "avg_after_median": sum(o["after_median"] for o in occurrences) / len(occurrences),
            "avg_delta_ms": sum(o["delta_ms"] for o in occurrences) / len(occurrences),
        })
    report.sort(key=lambda r: -r["avg_delta_ms"])
    return report


def load_key_stats_db(con):
    """Per-key frequency (raw press count) and per-key latency (median gap
    ending on that key), for the keyboard heatmap. The keylogger records the
    character actually typed, not the physical key + modifier state, so
    counts are aggregated through CHAR_TO_KEY (e.g. "!" and "1" both land on
    the "1" key, "E" lands on "e") before grouping. Grouping in SQL by the
    raw `key` column would keep those apart. Latency uses the same
    attempt-scoped LAG pairing and MAX_GAP_MS/MIN_SAMPLES rules as
    load_bigram_rows_db, but grouped by the destination key instead of the
    pair: "how slow is it to reach this key" rather than "how slow is this
    specific two-key sequence". Also matches load_bigram_rows_db in only
    counting events from Attempts matched to a real result - see that
    function's docstring for why unmatched Attempts (stray typing outside
    an actual test) get excluded here rather than just in the DB."""
    freq_by_key = {}
    for char, n in con.execute("""
        SELECT ke.key, count(*)
        FROM keylog_events ke
        JOIN attempts a ON a.attempt_id = ke.attempt_id
        WHERE length(ke.key) = 1 AND a.result_id IS NOT NULL
        GROUP BY ke.key
    """).fetchall():
        phys_key = CHAR_TO_KEY.get(char, char)
        freq_by_key[phys_key] = freq_by_key.get(phys_key, 0) + n

    gap_rows = con.execute(f"""
        WITH matched_events AS (
            SELECT ke.attempt_id, ke.ts_ms, ke.key
            FROM keylog_events ke
            JOIN attempts a ON a.attempt_id = ke.attempt_id
            WHERE a.result_id IS NOT NULL
        ),
        ordered AS (
            SELECT attempt_id, ts_ms, key,
                   LAG(key) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_key,
                   LAG(ts_ms) OVER (PARTITION BY attempt_id ORDER BY ts_ms) AS prev_ts
            FROM matched_events
        )
        SELECT key, ts_ms - prev_ts AS gap
        FROM ordered
        WHERE length(key) = 1 AND length(prev_key) = 1
          AND ts_ms - prev_ts > 0 AND ts_ms - prev_ts <= {MAX_GAP_MS}
    """).fetchall()

    gaps_by_key = {}
    for char, gap in gap_rows:
        phys_key = CHAR_TO_KEY.get(char, char)
        gaps_by_key.setdefault(phys_key, []).append(gap)
    latency_by_key = {
        phys_key: float(np.median(gaps))
        for phys_key, gaps in gaps_by_key.items()
        if len(gaps) >= MIN_SAMPLES
    }

    return freq_by_key, latency_by_key


# ---------------------------------------------------------------------------
# stats / insights
# ---------------------------------------------------------------------------


def linreg(x, y):
    """Return (slope, intercept, pearson_r). x, y are equal-length sequences."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or np.std(x) == 0:
        return 0.0, float(y[0]) if len(y) else 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1]) if np.std(y) > 0 else 0.0
    return float(slope), float(intercept), r


def compute_kpis(df):
    n = len(df)
    recent = df.tail(RECENT_N)
    first = df.head(RECENT_N)
    total_seconds = float(df["testDuration"].sum())

    # Monkeytype's API only includes restartCount on a result when it's
    # nonzero (confirmed against the DB: every non-null value is >= 1), so a
    # null here means "no restarts before this completed test", i.e. 0.
    restart_count = df["restart_count"].fillna(0)
    total_restarts = float(restart_count.sum())
    tests_started = n + total_restarts

    est_words_typed = float((df["wpm"] * (df["testDuration"] / 60)).sum())

    return {
        "n_tests": n,
        "est_words_typed": est_words_typed,
        "tests_started": tests_started,
        "completion_rate_pct": (n / tests_started * 100) if tests_started else 0.0,
        "restarts_per_test": float(restart_count.mean()) if n else 0.0,
        "best_wpm": float(df["wpm"].max()),
        "avg_wpm_all": float(df["wpm"].mean()),
        "avg_wpm_recent": float(recent["wpm"].mean()),
        "avg_wpm_first": float(first["wpm"].mean()),
        "best_raw_wpm": float(df["raw_wpm"].max()),
        "avg_raw_wpm_all": float(df["raw_wpm"].mean()),
        "avg_raw_wpm_recent": float(recent["raw_wpm"].mean()),
        "best_acc": float(df["acc"].max()),
        "avg_acc_recent": float(recent["acc"].mean()),
        "avg_acc_all": float(df["acc"].mean()),
        "best_consistency": float(df["consistency"].max()),
        "avg_consistency_recent": float(recent["consistency"].mean()),
        "avg_consistency_all": float(df["consistency"].mean()),
        "avg_errors_recent": float(recent["error_count"].mean()),
        "avg_errors_first": float(first["error_count"].mean()),
        "total_minutes_typing": total_seconds / 60,
        "date_span_days": (
            df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]
        ).total_seconds()
        / 86400,
    }


def compute_insights(df, bigram_rows):
    idx = np.arange(len(df))
    wpm_slope, _, wpm_r = linreg(idx, df["wpm"])
    acc_slope, _, _ = linreg(idx, df["acc"])

    half = len(df) // 2
    acc_std_first = float(df["acc"].iloc[:half].std()) if half >= 2 else None
    acc_std_second = float(df["acc"].iloc[half:].std()) if len(df) - half >= 2 else None

    acc_wpm_r = float(np.corrcoef(df["acc"], df["wpm"])[0, 1]) if len(df) >= 2 else 0.0
    acc_wpm_slope, acc_wpm_intercept, _ = linreg(df["wpm"], df["acc"])

    # Speed change per hour of practice: regress wpm against cumulative
    # practice time (test_duration summed up to and including each test,
    # in hours) rather than test index, so the slope reads as "wpm gained
    # per hour actually spent typing" instead of "wpm gained per test" -
    # a fairer trend given tests vary a lot in length (15s vs 120s vs quote).
    cumulative_hours = df["testDuration"].fillna(0).cumsum() / 3600
    wpm_per_hour_slope, _, _ = linreg(cumulative_hours, df["wpm"])

    return {
        "wpm_slope_per_test": wpm_slope,
        "wpm_trend_r": wpm_r,
        "acc_slope_per_test": acc_slope,
        "acc_std_first_half": acc_std_first,
        "acc_std_second_half": acc_std_second,
        "acc_wpm_correlation": acc_wpm_r,
        "acc_wpm_slope": acc_wpm_slope,
        "acc_wpm_intercept": acc_wpm_intercept,
        "wpm_per_hour_typing": wpm_per_hour_slope,
        "has_tags": False,  # set by caller once tag data is checked
        "bigram_rows": bigram_rows,
    }


def compute_popular_tests(df):
    def bucket(row):
        if row["mode"] == "quote":
            return ("quote", None)
        key = (row["mode"], str(row["mode2"]))
        return key if key in POPULAR_TESTS else ("other", None)

    df = df.copy()
    df["_bucket"] = df.apply(bucket, axis=1)

    rows = []
    for mode, mode2 in POPULAR_TESTS:
        sub = df[df["_bucket"] == (mode, mode2)]
        label = f"{mode} {mode2}" if mode2 else mode
        rows.append(
            {
                "label": label,
                "n": len(sub),
                "avg_wpm": float(sub["wpm"].mean()) if len(sub) else None,
                "avg_acc": float(sub["acc"].mean()) if len(sub) else None,
                "best_wpm": float(sub["wpm"].max()) if len(sub) else None,
            }
        )

    other = df[df["_bucket"] == ("other", None)]
    if len(other):
        rows.append(
            {
                "label": "other (custom/unrecognized)",
                "n": len(other),
                "avg_wpm": float(other["wpm"].mean()),
                "avg_acc": float(other["acc"].mean()),
                "best_wpm": float(other["wpm"].max()),
            }
        )

    return rows


def display_bigram(bigram):
    # A leading/trailing space (word-boundary bigrams like " b") collapses
    # under normal HTML whitespace rules and becomes indistinguishable from
    # a bare "b". Swap in a visible space glyph so it stays legible.
    return bigram.replace(" ", "␣")


def classify_bigram(bigram):
    """Tags a two-character bigram with the finger-mechanics categories it
    matches, using FINGER_MAP. Tags aren't mutually exclusive: a same-finger
    bigram that also skips two rows gets both "sfb" and "row_skip", matching
    how community keyboard-layout analyzers (Oxeylyzer, Cyanophage) report
    these as independent metrics rather than a single classification.
    Cross-hand bigrams and keys outside the letter grid (space, digits,
    most punctuation) never match anything here."""
    if len(bigram) != 2:
        return set()
    a, b = bigram
    if a not in FINGER_MAP or b not in FINGER_MAP or a == b:
        return set()
    hand_a, rank_a, row_a = FINGER_MAP[a]
    hand_b, rank_b, row_b = FINGER_MAP[b]
    if hand_a != hand_b:
        return set()

    tags = set()
    same_finger = rank_a == rank_b
    if same_finger:
        tags.add("sfb")
        if abs(row_a - row_b) >= 2:
            tags.add("row_skip")
    if row_b > row_a or (not same_finger and rank_b > rank_a):
        tags.add("awkward_roll")
    if not same_finger and (a in STRETCH_KEYS or b in STRETCH_KEYS):
        tags.add("lsb")
    return tags


def _weighted_median_and_representative(rows):
    """Approximates an occurrence-weighted median from per-bigram summary
    stats. bigram_rows only carries each bigram's own n/median/mean, not raw
    per-keystroke gaps, so the weighted median is approximated the same way
    overall_avg/category avg are weighted: expand each bigram's median by its
    occurrence count n (np.repeat) and take the median of that expanded
    population.

    Also returns the single bigram from `rows` whose own median sits closest
    to that weighted-median value - a concrete, named "representative"
    example (e.g. "bigram 'th' types at ~180ms") to serve as the baseline
    TODO.md asks tail/outlier sections to be measured against, rather than
    just an abstract number nothing in the data corresponds to."""
    if not rows:
        return None, None
    medians = [r["median"] for r in rows]
    weights = [r["n"] for r in rows]
    weighted_median = float(np.median(np.repeat(medians, weights)))
    representative = min(rows, key=lambda r: abs(r["median"] - weighted_median))
    return weighted_median, {
        "bigram": representative["bigram"],
        "median": representative["median"],
    }


def compute_bigram_ergonomics(bigram_rows):
    """Aggregate the same trustworthy bigrams (bigram_rows, already past
    MIN_SAMPLES) by finger-mechanics category. Each category's "avg" is an
    occurrence-weighted mean gap (sum(mean*n)/sum(n)) rather than a mean of
    medians, so it's a true average across every logged occurrence in that
    category and comparable to overall_avg, which is weighted the same way.

    "median"/"representative_bigram"/"representative_median" (and their
    overall_* counterparts) are the "representative" baseline: a
    less-outlier-skewed benchmark than the mean, paired with a concrete named
    bigram close to it, for the tail/outlier sections to compare against."""
    tags_by_bigram = {r["bigram"]: classify_bigram(r["bigram"]) for r in bigram_rows}

    total_n = sum(r["n"] for r in bigram_rows)
    overall_avg = (
        (sum(r["mean"] * r["n"] for r in bigram_rows) / total_n) if total_n else None
    )
    overall_median, overall_representative = _weighted_median_and_representative(bigram_rows)

    category_rows = []
    detail_rows = []
    for key, label, desc in BIGRAM_CATEGORIES:
        matches = [r for r in bigram_rows if key in tags_by_bigram[r["bigram"]]]
        n = sum(r["n"] for r in matches)
        avg = (sum(r["mean"] * r["n"] for r in matches) / n) if n else None
        delta_pct = (
            ((avg / overall_avg) - 1) * 100 if avg is not None and overall_avg else None
        )
        median, representative = _weighted_median_and_representative(matches)
        category_rows.append(
            {
                "key": key,
                "label": label,
                "desc": desc,
                "distinct": len(matches),
                "n": n,
                "avg": avg,
                "delta_pct": delta_pct,
                "median": median,
                "representative_bigram": representative["bigram"] if representative else None,
                "representative_median": representative["median"] if representative else None,
            }
        )
        for r in sorted(matches, key=lambda r: -r["median"])[:5]:
            detail_rows.append({"category": label, **r})

    return overall_avg, overall_median, overall_representative, category_rows, detail_rows


def compute_action_plan(kpis, insights, has_tags):
    actions = []

    if (
        insights["acc_std_first_half"] is not None
        and insights["acc_std_second_half"] is not None
    ):
        stabilizing = (
            insights["acc_std_second_half"] < insights["acc_std_first_half"] * 0.85
        )
    else:
        stabilizing = None

    if kpis["avg_acc_recent"] < 90:
        actions.append(
            {
                "status": "warning",
                "text": f"Recent accuracy is averaging {kpis['avg_acc_recent']:.1f}%, below the "
                "90% floor generally considered safe for pushing speed. Slow down slightly "
                "on the next sessions and let accuracy settle before chasing WPM.",
            }
        )
    elif stabilizing is False:
        actions.append(
            {
                "status": "warning",
                "text": f"Accuracy is averaging {kpis['avg_acc_recent']:.1f}% but its spread hasn't "
                "tightened. Variance in the second half of your tests isn't lower than the "
                "first half, so it's high but not yet locked in. Keep an eye on it before "
                "treating speed as the only lever.",
            }
        )
    else:
        actions.append(
            {
                "status": "good",
                "text": f"Accuracy is averaging {kpis['avg_acc_recent']:.1f}% and stable. You're clear "
                "to focus on speed rather than accuracy for now.",
            }
        )

    if kpis["avg_wpm_recent"] > kpis["avg_wpm_first"]:
        actions.append(
            {
                "status": "good",
                "text": f"WPM is up from {kpis['avg_wpm_first']:.1f} (first {RECENT_N} tests) to "
                f"{kpis['avg_wpm_recent']:.1f} (last {RECENT_N}). Whatever you're doing is "
                "working, keep the volume up.",
            }
        )
    else:
        actions.append(
            {
                "status": "warning",
                "text": f"WPM hasn't moved from {kpis['avg_wpm_first']:.1f} (first {RECENT_N} tests) to "
                f"{kpis['avg_wpm_recent']:.1f} (last {RECENT_N}). That's a plateau signal. "
                "Consider targeted weak-bigram drilling instead of more undifferentiated volume.",
            }
        )

    bigram_rows = insights["bigram_rows"]
    if bigram_rows:
        top = bigram_rows[:5]
        names = ", ".join(f"'{display_bigram(r['bigram'])}'" for r in top)
        actions.append(
            {
                "status": "good",
                "text": f"Slowest bigrams with enough samples to trust: {names}. These are the "
                "concrete drill candidates. Build a Monkeytype custom word list that "
                "overloads these specific sequences.",
            }
        )
    else:
        actions.append(
            {
                "status": "warning",
                "text": "No bigram data has cleared the minimum sample threshold yet. Keep the "
                "keylogger running across more sessions before trusting a drill list.",
            }
        )

    if not has_tags:
        actions.append(
            {
                "status": "serious",
                "text": "Volume-vs-drilling and hand-position A/B are still unanswered. Both need "
                "tagged sessions (Monkeytype's `tags` field), and none of your synced results "
                "have one yet. Start tagging sessions if you want those questions closed out.",
            }
        )

    return actions
