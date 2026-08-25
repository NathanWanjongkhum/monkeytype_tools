Practicing on Monkeytype (10k english, stop on word). Gathering what's actually known beyond "just type more."

## Practice amount vs deliberate practice
Large study of 1301 university students (PMC9356123) found accumulated keyboard use was the strongest predictor of proficiency, not intentional practice.
- Most proficient: 2.4±2.1 hrs/day, 10.3±4.3 yrs experience → 80 WPM (IQR 20), 88% accuracy
- Least proficient: 1.7±1.7 hrs/day, 9.2±4.7 yrs experience → 54 WPM (IQR 18), 79% accuracy
- "Deliberate practice" (self-reported intentional improvement effort) had no significant effect (p=0.70). Incidental typing volume did the work.
- Most proficient typists used more fingers (7.3±1.9 vs 6.9±1.9) and almost never looked at the keyboard

This contradicts the elite-typist community claim (Colemak/Typecelerate circles) that **targeted weak-bigram/trigram drilling** is what breaks plateaus: isolate your slowest 2-3 char sequences and drill them for a few minutes at a time instead of repeating whole passages. Both are plausibly true at different skill levels. Incidental volume gets you to competent; targeted drilling gets you past a plateau once broad practice stops moving the number.

## Rollover and anticipation
Aalto/Cambridge study of 168k typists, 136M keystrokes (CHI 2018):
- Fastest typists rely on **rollover**, pressing the next key before releasing the previous one. Fast typists roll over 40-70% of keystrokes.
- Rollover only works for highly practiced, frequent letter combinations, and only when you're not relying on vision to find the next key. It's downstream of not looking at the keyboard, not a separate technique.
- Bimanual transitions (alternating hands) are ~0.17ms faster per keystroke than same-hand transitions
- Frequent bigrams reduce inter-keystroke interval by ~0.056ms per log-unit of frequency, effect stronger in proficient typists. Drilling common bigrams pays off more than rare ones, since gains compound with frequency.
- Peripheral vision use (not fixating the keys or the screen) measured ~28% faster typing vs fixating

## Speed-accuracy tradeoff
Yamaguchi, Crump & Logan (2013, skilled typewriting) found typists can trade speed for accuracy but can't exceed ~100ms/keystroke regardless. That's a hard floor from the underlying motor control loop, not a skill ceiling.
- Practical implication repeated across typing-coaching sources: accuracy plateaus early and holds; once accuracy is stable (~90-95%+), further practice converts almost entirely into speed gains with error rate held constant
- Fixing a wrong motor pattern learned at high error rates costs more than learning correctly slow. Matches general motor learning literature, not typing-specific.

## Hand position / finger curl
No direct study found on your "hands further back, fingers more curled" observation, but it fits known biomechanics.
- Curling the fingers changes which joint does the reaching. Instead of moving the whole hand/wrist to reach a row, the phalangeal joints do more of the work, and that's a shorter, faster lever.
- Confirms your read: top-row and c/x-type reaches with stretched fingers cost more wrist deviation when hands sit close/flat. Curled and back trades wrist travel for finger-joint travel, which is the joint built for fast repeated motion.
- This is your own finding, not something I found in the literature. Worth writing up precisely (hand distance from home row, curl angle) since it looks like a real gap between community advice and formal research.

## Ergonomics / RSI (indirect speed effect via fatigue/error rate, not raw motor speed)
- Neutral wrist means no flexion/extension/ulnar deviation. Split/tented keyboards measured to reduce ulnar deviation from ~12° to within 5° of neutral (vs standard keyboard)
- 5-month split+tented keyboard study: significant reduction in self-reported discomfort vs standard keyboard control group
- Effect on speed is indirect. Less fatigue keeps error rate low over a long session, so WPM doesn't decay late on. Not a source of raw peak-speed gain.

## Keyboard layout (QWERTY vs Colemak/Dvorak)
No reliable evidence of a causal speed advantage.
- Modern estimates put Colemak/Dvorak ~5-10% ahead of QWERTY at expert level, but no controlled study rules out selection effects (people motivated enough to relearn a layout are unusually motivated typists to begin with)
- Dvorak's own 1930s claim of 70% faster was never independently replicated; a 1956 Strong study found QWERTY-fluent typists retrained on Dvorak recovered their old speed but didn't reliably beat it
- 2020 Ultimate Typing Championship: all top 10 quarterfinalists on QWERTY
- Relearning cost is real and front-loaded: Dvorak ~3mo to match old QWERTY speed, ~6mo to exceed it; Colemak ~6-8wk to match, ~3-4mo to exceed
- No proven speed ceiling gain against a multi-month relearning cost. Not worth it purely for WPM, only makes sense for RSI/ergonomic reasons.

## Hardware (switches, actuation force/distance)
Weak, mostly confounded effects.
- Actuation force ranges ~35-80cN, travel ~2-4mm. Theoretical savings from shorter travel are single-digit milliseconds per keystroke, too small to move measured WPM.
- Where mechanical keyboards do help: comfort and lower error rate over long sessions (less finger fatigue after ~30min), which protects WPM late-session through the same fatigue mechanism as the ergonomics section above.
- No causal evidence mechanical beats membrane for peak WPM in controlled tests

## Open questions to test myself
- Precisely characterize the hand-position finding: home-row distance, finger curl angle, which rows/keys it helps most (top row, x/c/z column). Could be a genuinely novel note since I couldn't find it published.
- Test weak-bigram drilling against raw volume practice on my own Monkeytype stats over a few weeks. The PMC study and the elite-typist community claim disagree, worth resolving for myself.
- Track error rate alongside WPM to confirm the "accuracy first, then speed" pattern actually holds at my current level

## Testing with existing Monkeytype data
Monkeytype already stores per-test results server-side and exposes them via `GET https://api.monkeytype.com/results` (auth header `Authorization: ApeKey <key>`, generated in Settings > Danger Zone > Ape Keys). Paginated with `limit`/`offset`/`onOrAfterTimestamp`. Per result:
- `wpm`, `rawWpm`, `acc`, `consistency`
- `charStats`: [correct, incorrect, extra, missed]
- `testDuration`, `afkDuration`, `timestamp`, `mode`, `mode2`, `language`, `difficulty`, `tags`, `punctuation`/`numbers` flags
- `chartData`: `wpm[]`, `raw[]`, `err[]` per-second within the test (tests over 122s just store "toolong")
- `keySpacingStats` and `keyDurationStats`: `{average, sd}`, but only aggregated over the whole test

The limitation that matters: Monkeytype captures per-keystroke timing internally for its replay feature and anti-cheat checks, but only exposes test-level aggregates through the account, export, and API. There's no per-character or per-bigram breakdown in the data you can actually pull. So bigram-specific claims (which sequences are slow for me) can't be tested from exported data directly, only from cruder test-level proxies.

What test-level data alone can answer:
- **Volume vs targeted drilling.** Use the `tags` field: tag ordinary 10k-stop-word sessions one way, tag dedicated custom-word-list drill sessions (word lists overloaded with specific bigrams or columns) another way. Pull results, fit wpm against cumulative time-typing per tag, compare slopes.
- **Accuracy-first hypothesis.** Plot acc vs wpm across history ordered by timestamp. Check whether acc variance shrinks and flattens while wpm keeps trending up.
- **Rhythm/chunking link.** Track `consistency` and `keySpacingStats.sd` over time. If motor chunking is forming, sd should fall as wpm rises.
- **Fatigue/ergonomics proxy.** For longer tests, `chartData.wpm[]` shows within-test decay. Compare decay slope before and after an ergonomics change, like the hand-position adjustment.
- **Hand-position A/B.** Tag sessions "hands-back" vs "hands-normal" for a stretch and compare wpm/acc distributions. Monkeytype can't sense hand position itself, so this only works if I tag consistently.

What test-level data can't answer: which specific bigrams are actually slow, or anything about finger path/curl. Those need either manual judgment (which words trip me up) or real instrumentation.

Bridge option before a camera rig: Monkeytype is just a webpage, so a userscript (Tampermonkey) with a `keydown` listener during a test can log per-character timestamp, key, and best-effort correctness locally as JSON. That gives real per-bigram inter-key intervals without any computer vision, much cheaper than the camera idea, and it isolates the timing question (which bigrams are slow) from the harder biomechanics question (finger path/curl) that actually needs a camera later.

**Tools**: code lives in `~/dev/monkeytype_tools` (moved out of the vault, this is a code project not a note), split into `backend/` (Python: data pipeline + API server), `frontend/` (Vue 3 + TS dashboard app), and `data/` (all fetched/derived data - results JSON/CSV, keylogs, typing.duckdb, drill lists - kept separate from both).
- `backend/fetch_monkeytype_results.py` pulls the full result history via the API above into JSON + a timestamp-sorted CSV, for the trend/tag comparisons.
- `monkeytype-keylogger.user.js` is a Tampermonkey script, only active on monkeytype.com: logs every keystroke's timestamp and saves a session file (self-describing: `schema_version`, `session_id`, `part`, `url`, `saved_at`, `config`, `events`) into `<Downloads>/monkeytype-keylogs/<date>/` every 3 minutes, plus a best-effort final save when the tab closes. `Ctrl+Shift+E` forces an immediate save. `config` is Monkeytype's own `localStorage` settings snapshot at save time (mode, word/time target, punctuation, numbers, difficulty, layout, funbox, blindMode, freedomMode, stopOnError, ...) - captures which test/settings the keystrokes were actually typed under, including keyboard layout, which is what the layout-switching open question needs. Not yet consumed by the analysis scripts, just captured for future segmentation.
- Periodically move/clean up that Downloads folder into `data/keylogs/` inside the tools dir, e.g. `mv ~/Downloads/monkeytype-keylogs/* data/keylogs/`.
- `backend/analyze_keylog.py` scans `data/keylogs/` (or takes explicit file paths) and prints a sorted per-bigram median-latency table, i.e. which specific bigrams are actually slow for me.
- `backend/generate_dashboard.py` is the single entry point: `python3 backend/generate_dashboard.py` pulls fresh Monkeytype results, imports any new keylog sessions sitting in Downloads, force-rebuilds `data/typing.duckdb`, makes sure the API server and the Vite dev server for the dashboard (WPM/accuracy KPIs, WPM-over-time and accuracy-vs-WPM charts, bigram latency table, computed insights, a rule-based action plan, a status check against each open question above) are running, and opens it in a browser. `--offline` skips the refresh and rebuilds from whatever's already local; `--no-open` skips launching the browser. Opening the dashboard itself also refreshes and re-derives the database, but only when the underlying data actually changed. `fetch_monkeytype_results.py`/`import_keylogs.py` still work standalone if needed, but running the dashboard script is the normal path now - it reads the ApeKey from `backend/.env` automatically and degrades to stale local data instead of failing if the API/Downloads aren't reachable.

## References
- [Typing expertise in a large student population (PMC9356123)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9356123/)
- [Observations on Typing from 136 Million Keystrokes (CHI 2018)](https://dl.acm.org/doi/10.1145/3173574.3174220)
- [Speed–Accuracy Trade-Off in Skilled Typewriting (Yamaguchi, Crump, Logan 2013)](http://www.psy.vanderbilt.edu/faculty/logan/YamaguchiCrumpLogan2013.pdf)
- [How We Type: Movement Strategies and Performance in Everyday Typing (CHI 2016)](https://dl.acm.org/doi/10.1145/2858036.2858233)
- [Wrist and forearm posture from typing on split and vertically inclined computer keyboards (PubMed)](https://pubmed.ncbi.nlm.nih.gov/10774127/)
- [QWERTY vs. Dvorak vs. Colemak Keyboard Layouts (Das Keyboard)](https://www.daskeyboard.com/blog/qwerty-vs-dvorak-vs-colemak-keyboard-layouts)
