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
import re
from pathlib import Path

import db as typing_db

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
WORDLIST_PATH = HERE / "assets" / "english_10k.json"
OUT_PATH = DATA_DIR / "drill_practice.txt"

TARGET_BIGRAMS_N = 20      # how many of your slowest qualifying bigrams to *consider*
TARGET_WORDS_N = 50        # word budget for one generated test; caps how many of those get drilled
CATEGORY_TARGET_BIGRAMS_N = 8  # fewer per category, since there are 4 categories, not 1
MIN_REPEAT, MAX_REPEAT = 3, 15
MIN_WORDS_PER_BIGRAM, MAX_WORDS_PER_BIGRAM = 1, 4  # phrase length, inverse of repeat
WORD_RE = re.compile(r"^[a-z]+$")


def load_wordlist():
    if not WORDLIST_PATH.exists():
        raise SystemExit(
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


def words_containing(wordlist, bigram, limit):
    out = []
    for w in wordlist:
        if bigram in w:
            out.append(w)
            if len(out) >= limit:
                break
    return out


def build_drill_entries(bigram_rows, wordlist, target_n=TARGET_BIGRAMS_N, words_budget=TARGET_WORDS_N):
    """Pick the slowest qualifying bigrams (bigram_rows is already sorted
    slowest-first and past MIN_SAMPLES, same as the dashboard's "Slowest
    bigrams" table), find real Monkeytype-list words containing each, and
    weight both repeat count and phrase length by how much slower that
    bigram is than the fastest one in the pool: the worst bigrams get a
    short phrase repeated often (a tight rote loop to groove the motion),
    while near-miss bigrams get a longer, more varied phrase repeated only
    a few times (context coverage instead of rote drilling). Since drills
    regenerate from fresh typing data, a bigram graduates from the tight
    loop toward the varied phrase on its own as it gets faster.

    `target_n` only bounds how many bigrams are *candidates* — the loop below
    stops adding entries once `words_budget` total words have been placed, so
    a single generated test stays a test-sized paste (one MIN_REPEAT..MAX_REPEAT
    x MIN_WORDS_PER_BIGRAM..MAX_WORDS_PER_BIGRAM entry per qualifying bigram,
    stacked up to the budget) rather than growing unbounded with target_n."""
    targets = [r for r in bigram_rows if len(r["bigram"]) == 2][:target_n]
    if not targets:
        return [], []

    fastest_median = min(r["median"] for r in targets)
    entries, skipped = [], []
    words_used = 0
    for r in targets:
        remaining = words_budget - words_used
        if remaining <= 0:
            break
        weight = r["median"] / fastest_median
        repeat = max(MIN_REPEAT, min(MAX_REPEAT, round(MIN_REPEAT * weight)))
        words_n = max(MIN_WORDS_PER_BIGRAM, min(MAX_WORDS_PER_BIGRAM, round(MAX_WORDS_PER_BIGRAM / weight)))
        words = words_containing(wordlist, r["bigram"], words_n)
        if not words:
            skipped.append(r["bigram"])
            continue
        # Clip repeat (never below 1) so a single entry can't blow the
        # remaining budget, rather than dropping the whole bigram over it.
        if len(words) * repeat > remaining:
            repeat = max(1, remaining // len(words))
        entries.append({"bigram": r["bigram"], "phrase": " ".join(words), "repeat": repeat})
        words_used += len(words) * repeat
    return entries, skipped


def render_drill_text(entries):
    return "|".join("|".join([e["phrase"]] * e["repeat"]) for e in entries)


def generate(bigram_rows, out_path=OUT_PATH):
    """Writes out_path and returns the same drill text, so callers that need
    the text in-memory (the dashboard's copy button) don't have to re-read
    the file back off disk."""
    from dashboard_data import display_bigram

    wordlist = load_wordlist()
    entries, skipped = build_drill_entries(bigram_rows, wordlist)
    if not entries:
        print("[drill] no qualifying bigrams yet, skipping drill list")
        return None

    text = render_drill_text(entries)
    out_path.write_text(text)
    print(f"[drill] wrote {out_path} targeting {len(entries)} bigrams: "
          f"{', '.join(display_bigram(e['bigram']) for e in entries)}")
    if skipped:
        print(f"[drill] skipped (no dictionary match): "
              f"{', '.join(display_bigram(b) for b in skipped)}")
    return text


def build_category_drills(bigram_rows, wordlist):
    """Same slowest-first, repeat-weighted approach as build_drill_entries,
    but split into one drill list per finger-mechanics category
    (dashboard_data.BIGRAM_CATEGORIES) instead of one list mixing every
    mechanic together, so you can drill "just same-finger bigrams" on their
    own. Returns one dict per category, in BIGRAM_CATEGORIES order, whether
    or not it ended up with any qualifying bigrams."""
    from dashboard_data import BIGRAM_CATEGORIES, classify_bigram

    tags_by_bigram = {r["bigram"]: classify_bigram(r["bigram"]) for r in bigram_rows}
    drills = []
    for key, label, desc in BIGRAM_CATEGORIES:
        matches = sorted(
            (r for r in bigram_rows if key in tags_by_bigram.get(r["bigram"], ())),
            key=lambda r: -r["median"],
        )
        entries, skipped = build_drill_entries(matches, wordlist, target_n=CATEGORY_TARGET_BIGRAMS_N)
        text = render_drill_text(entries) if entries else None
        drills.append({
            "key": key, "label": label, "desc": desc,
            "entries": entries, "skipped": skipped, "text": text,
        })
    return drills


def generate_category_drills(bigram_rows, out_dir=DATA_DIR):
    """Like generate(), but writes one drill_practice_<category>.txt per
    finger-mechanics category and returns all four dicts (from
    build_category_drills) with a "path" filename added wherever a drill
    list was actually written."""
    from dashboard_data import display_bigram

    wordlist = load_wordlist()
    drills = build_category_drills(bigram_rows, wordlist)
    for d in drills:
        if not d["text"]:
            print(f"[drill] {d['label']}: no qualifying bigrams yet, skipping")
            continue
        path = out_dir / f"drill_practice_{d['key']}.txt"
        path.write_text(d["text"])
        d["path"] = path.name
        print(f"[drill] wrote {path} targeting {len(d['entries'])} bigrams: "
              f"{', '.join(display_bigram(e['bigram']) for e in d['entries'])}")
    return drills


def main():
    from dashboard_data import load_bigram_rows_db

    con = typing_db.connect()
    bigram_rows, _, _ = load_bigram_rows_db(con)
    con.close()
    generate(bigram_rows)


if __name__ == "__main__":
    main()
