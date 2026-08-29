# Drill design

`generate_drill_list.py` builds one drill entry per targeted bigram — a phrase of dictionary words containing it, repeated `repeat` times. Selection and time-allocation are now driven by an **impact score** combining how often a bigram occurs with how much slower it is than it should be, replacing pure latency-based ranking: maximizing real-world WPM means prioritizing common bottlenecks over rare ones, regardless of how slow a rare one looks in isolation.

## Frequency weight

No bigram-frequency corpus exists in the project. Frequency is approximated from `backend/assets/english_10k.json` — the same word list `words_containing` already draws phrase words from — which is rank-ordered, not counted. A bigram's frequency weight is the sum, over every word in the list containing it, of `1 / log(rank + 2)`: log-rank decay, so a bigram in "the" counts far more than one only in "xylophone," without a single top-50 word being able to dwarf the entire pool the way a literal `1/rank` weighting would.

## Latency signal

`median` per bigram is shrunk toward the pool-wide mean, in proportion to how close its sample count `n` is to the `MIN_SAMPLES = 5` floor. `MIN_SAMPLES` still gates pool entry outright — shrinkage only tempers noise among bigrams that already cleared it, so a bigram sitting at `n = 5` can no longer claim a precise "slowest in the pool" ranking off five samples alone.

## Impact score

`impact = frequency_weight × (shrunk_median − fastest_shrunk_median)` — frequency times room-for-improvement, not frequency times raw speed. This single score:

- Selects the top `TARGET_BIGRAMS_N` overall, and top `CATEGORY_TARGET_BIGRAMS_N` within each of the four category drills (`sfb`, `row_skip`, `awkward_roll`, `lsb`).
- Replaces `weight` in the `repeat`/`words_n` formulas, normalized back onto the old ~1.0-centered relative scale (`impact / mean(impact)` across the selected set) so `repeat = clamp(3, 15, round(3 × ratio))` and `words_n = clamp(1, 4, round(4 / ratio))` — and their existing rationale (tight rote loop for the worst offender, a context-check phrase for one that barely qualifies) — carry over unchanged. Only what counts as "worst" changes.

This is a theoretical proxy for real WPM improvement, not a guarantee — see [0003-drill-completion-validation.md](0003-drill-completion-validation.md) for how it's checked against observed latency change.

## Considered alternatives

- **Fixed time-budget allocation** — spending a fixed total `repeat` budget across bigrams to explicitly maximize predicted ∆WPM/hour, the most literal reading of "optimize training time for WPM impact." Deferred: it reopens the unit-mismatch failure behind the reverted word-budget cap (`045a731` / `e57e83a`), which constrained dictionary-word count while Monkeytype's own test-length target operates on pipe-segment (`repeat`) count. Re-ranking by impact captures most of the benefit without also having to solve session-length budgeting correctly.
- **Pure inverse rank (`1/rank`, literal Zipfian)** for frequency weight — more mathematically "authentic," but too top-heavy: a bigram appearing only in a handful of top-50 words could dwarf everything else in the pool.
- **Frequency × raw latency** instead of excess latency — simpler, but lets a common, merely-average-speed bigram outrank a rare, genuinely-bad one, which isn't measuring room for improvement.
