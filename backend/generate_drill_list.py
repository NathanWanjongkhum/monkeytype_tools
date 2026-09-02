#!/usr/bin/env python3
"""Builds a Monkeytype-pasteable custom word list targeting your slowest
bigrams. Monkeytype's own word filter (Settings > word filter) can only
select whole words by length/regex/preset. It has no "contains this
bigram" option, so this generates the list ourselves from real words in
Monkeytype's own english_10k list (assets/english_10k.json), instead of
relying on the site's filter.

Paste the output of drill_practice.txt into Monkeytype's custom text box
(the "custom" test mode) with word delimiter set to "pipe". See
assets/example.txt for what that pasted format looks like. Words are
repeated in place (matching that format) rather than relying on Monkeytype's
own "repeat" test mode, so a "shuffle" or "random" mode still oversamples
the worst bigrams regardless of which words get picked.

Usage:
    python3 generate_drill_list.py             # regenerate drill_practice.txt
"""

import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import db as typing_db
from dashboard_data import (
    BIGRAM_CATEGORIES,
    MIN_SAMPLES,
    classify_bigram,
    display_bigram,
    load_bigram_rows_db,
)

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
WORDLIST_PATH = HERE / "assets" / "english_10k.json"
OUT_PATH = DATA_DIR / "drill_practice.txt"

TARGET_BIGRAMS_N = 20  # how many of your slowest qualifying bigrams to drill
CATEGORY_TARGET_BIGRAMS_N = 8  # fewer per category, since there are 4 categories, not 1
MIN_REPEAT, MAX_REPEAT = 3, 15
MIN_WORDS_PER_BIGRAM, MAX_WORDS_PER_BIGRAM = 1, 4  # phrase length, inverse of repeat
WORD_RE = re.compile(r"^[a-z]+$")
BIGRAM_LEN = 2


def load_wordlist() -> list[str]:
    if not WORDLIST_PATH.exists():
        sys.exit(
            f"{WORDLIST_PATH} not found. Fetch Monkeytype's word list once with:\n"
            f'  curl -sL -o "{WORDLIST_PATH}" '
            f'"https://raw.githubusercontent.com/monkeytypegame/monkeytype/master/frontend/static/languages/english_10k.json"'
        )
    data = json.loads(WORDLIST_PATH.read_text())
    # Already ordered by frequency, most common first (the source file's own
    # "orderedByFrequency" flag). Preserving that order means "first K
    # matches" below picks common, natural words to type rather than
    # obscure ones that happen to share the bigram.
    return [w.lower() for w in data["words"] if WORD_RE.match(w.lower())]


def words_containing(wordlist: list[str], bigram: str, limit: int) -> list[str]:
    out = []
    for w in wordlist:
        if bigram in w:
            out.append(w)
            if len(out) >= limit:
                break
    return out


def build_bigram_frequency_weights(wordlist: list[str]) -> dict[str, float]:
    """Approximates each bigram's real-world frequency from Monkeytype's own
    word list order, since no bigram-frequency corpus exists in this project
    and the list only carries word rank, not raw counts. Weight is the sum,
    over every word containing the bigram, of 1/log(rank + 2) - log-rank
    decay, so a bigram in "the" counts far more than one only in
    "xylophone", without a single top-50 word being able to dwarf the whole
    pool the way a literal 1/rank weighting would. See
    docs/adr/0002-drill-design.md."""
    weights: dict[str, float] = {}
    for rank, word in enumerate(wordlist):
        contribution = 1 / math.log(rank + 2)
        for bg in {word[i : i + 2] for i in range(len(word) - 1)}:
            weights[bg] = weights.get(bg, 0.0) + contribution
    return weights


def build_drill_entries(
    bigram_rows: list[dict[str, Any]],
    wordlist: list[str],
    target_n: int = TARGET_BIGRAMS_N,
    frequency_weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Picks the highest-*impact* qualifying bigrams rather than the
    slowest: impact = frequency (how often the bigram actually occurs,
    approximated from Monkeytype's own word list) times excess latency
    (how much slower than the fastest bigram in this pool, after shrinking
    each median toward the pool average in proportion to how few samples
    back it - so a bigram sitting right at MIN_SAMPLES can't claim a
    precise "worst" ranking off noise alone). See
    docs/adr/0002-drill-design.md.

    Repeat count and phrase length are then weighted by that same impact
    score, normalized back onto a ~1.0-centered relative scale: the worst
    offender gets a short phrase repeated often (a tight rote loop to
    groove the motion), while a near-miss gets a longer, more varied
    phrase repeated only a few times (context coverage instead of rote
    drilling). Since drills regenerate from fresh typing data, a bigram
    graduates from the tight loop toward the varied phrase on its own as
    it gets faster."""
    # Copy each row rather than reusing bigram_rows' own dicts: below mutates
    # candidates in place to attach shrunk_median/impact, and bigram_rows is
    # also handed to compute_bigram_ergonomics and serialized as-is in the
    # API payload - it must come back out exactly as it went in.
    candidates = [dict(r) for r in bigram_rows if len(r["bigram"]) == BIGRAM_LEN]
    if not candidates:
        return [], []
    frequency_weights = frequency_weights or {}

    pool_mean = sum(r["median"] for r in candidates) / len(candidates)
    for r in candidates:
        r["shrunk_median"] = (r["n"] * r["median"] + MIN_SAMPLES * pool_mean) / (
            r["n"] + MIN_SAMPLES
        )
    fastest_shrunk = min(r["shrunk_median"] for r in candidates)
    for r in candidates:
        freq = frequency_weights.get(r["bigram"], 0.0)
        r["impact"] = freq * (r["shrunk_median"] - fastest_shrunk)

    targets = sorted(candidates, key=lambda r: -r["impact"])[:target_n]
    if not targets:
        return [], []

    mean_impact = sum(r["impact"] for r in targets) / len(targets)
    entries: list[dict[str, Any]] = []
    skipped: list[str] = []
    for r in targets:
        ratio = r["impact"] / mean_impact if mean_impact > 0 else 1.0
        repeat = max(MIN_REPEAT, min(MAX_REPEAT, round(MIN_REPEAT * ratio)))
        words_n = (
            MAX_WORDS_PER_BIGRAM
            if ratio <= 0
            else max(
                MIN_WORDS_PER_BIGRAM, min(MAX_WORDS_PER_BIGRAM, round(MAX_WORDS_PER_BIGRAM / ratio))
            )
        )
        words = words_containing(wordlist, r["bigram"], words_n)
        if not words:
            skipped.append(r["bigram"])
            continue
        entries.append({"bigram": r["bigram"], "phrase": " ".join(words), "repeat": repeat})
    return entries, skipped


def render_drill_text(entries: list[dict[str, Any]]) -> str:
    phrases: list[str] = ["|".join([str(e["phrase"])] * e["repeat"]) for e in entries]
    return "|".join(phrases)


def write_manifest(drill_path: Path, key: str, label: str, entries: list[dict[str, Any]]) -> None:
    """Sidecar JSON next to a drill_practice*.txt, recording which bigrams
    that specific generation actually targeted. render_drill_text collapses
    entries down to flat pipe-delimited text with no bigram identity left in
    it, and /api/dashboard regenerates these files from live DB state on
    every request - so anything that needs to know "what was in this drill"
    later (docs/adr/0003-drill-completion-validation.md) has to read this
    manifest, not re-derive it from whatever the files currently contain."""
    manifest = {
        "key": key,
        "label": label,
        "bigrams": [e["bigram"] for e in entries],
        "generated_at": datetime.now(UTC).isoformat(),
    }
    drill_path.with_suffix(".json").write_text(json.dumps(manifest))


def generate(bigram_rows: list[dict[str, Any]], out_path: Path = OUT_PATH) -> str | None:
    """Writes out_path and returns the same drill text, so callers that need
    the text in-memory (the dashboard's copy button) don't have to re-read
    the file back off disk."""
    wordlist = load_wordlist()
    frequency_weights = build_bigram_frequency_weights(wordlist)
    entries, skipped = build_drill_entries(
        bigram_rows, wordlist, frequency_weights=frequency_weights
    )
    if not entries:
        print("[drill] no qualifying bigrams yet, skipping drill list")
        return None

    text = render_drill_text(entries)
    out_path.write_text(text)
    write_manifest(out_path, key="overall", label="Overall", entries=entries)
    print(
        f"[drill] wrote {out_path} targeting {len(entries)} bigrams: "
        f"{', '.join(display_bigram(e['bigram']) for e in entries)}"
    )
    if skipped:
        print(
            f"[drill] skipped (no dictionary match): "
            f"{', '.join(display_bigram(b) for b in skipped)}"
        )
    return text


def build_category_drills(
    bigram_rows: list[dict[str, Any]],
    wordlist: list[str],
    frequency_weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Same impact-weighted approach as build_drill_entries, but split into
    one drill list per finger-mechanics category (dashboard_data.
    BIGRAM_CATEGORIES) instead of one list mixing every mechanic together,
    so you can drill "just same-finger bigrams" on their own. Each
    category ranks by impact within its own pool, so a frequent-but-awkward
    bigram outranks a rare one within its category too. Returns one dict
    per category, in BIGRAM_CATEGORIES order, whether or not it ended up
    with any qualifying bigrams."""
    tags_by_bigram = {r["bigram"]: classify_bigram(r["bigram"]) for r in bigram_rows}
    drills: list[dict[str, Any]] = []
    for key, label, desc in BIGRAM_CATEGORIES:
        matches = [r for r in bigram_rows if key in tags_by_bigram.get(r["bigram"], ())]
        entries, skipped = build_drill_entries(
            matches,
            wordlist,
            target_n=CATEGORY_TARGET_BIGRAMS_N,
            frequency_weights=frequency_weights,
        )
        text = render_drill_text(entries) if entries else None
        drills.append(
            {
                "key": key,
                "label": label,
                "desc": desc,
                "entries": entries,
                "skipped": skipped,
                "text": text,
            }
        )
    return drills


def generate_category_drills(
    bigram_rows: list[dict[str, Any]], out_dir: Path = DATA_DIR
) -> list[dict[str, Any]]:
    """Like generate(), but writes one drill_practice_<category>.txt per
    finger-mechanics category and returns all four dicts (from
    build_category_drills) with a "path" filename added wherever a drill
    list was actually written."""
    wordlist = load_wordlist()
    frequency_weights = build_bigram_frequency_weights(wordlist)
    drills = build_category_drills(bigram_rows, wordlist, frequency_weights=frequency_weights)
    for d in drills:
        if not d["text"]:
            print(f"[drill] {d['label']}: no qualifying bigrams yet, skipping")
            continue
        path = out_dir / f"drill_practice_{d['key']}.txt"
        path.write_text(d["text"])
        write_manifest(path, key=d["key"], label=d["label"], entries=d["entries"])
        d["path"] = path.name
        print(
            f"[drill] wrote {path} targeting {len(d['entries'])} bigrams: "
            f"{', '.join(display_bigram(e['bigram']) for e in d['entries'])}"
        )
    return drills


def main() -> None:
    con = typing_db.connect()
    bigram_rows, _, _ = load_bigram_rows_db(con)
    con.close()
    generate(bigram_rows)


if __name__ == "__main__":
    main()
