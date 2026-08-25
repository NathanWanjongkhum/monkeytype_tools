# Monkeytype Tools

Personal typing-analytics tooling for one Monkeytype account: pulls test history from the Monkeytype API and per-keystroke timing from a local keylogger userscript, and turns both into a dashboard.

## Language

**Result**:
A single completed Monkeytype test, as recorded by the Monkeytype API (wpm, accuracy, consistency, timestamp, mode, tags, ...). One Result = one finished test on Monkeytype's servers.
_Avoid_: Test, Score

**Session**:
A single browser-tab-open period during which the keylogger userscript was capturing keystrokes, saved to one or more part files every ~3 minutes or on tab close. A Session is not aligned 1:1 with a Result — it can span several Results (or none, e.g. idle time, settings changes).
_Avoid_: Test session, run

**Attempt**:
A segmented, time-bounded run of Events pulled out of a Session, hypothesized to correspond to one Result. Not every Attempt matches a Result — custom/unfinished practice typing and sync gaps produce Attempts that stay unmatched, and are still kept since the raw timing is still useful for bigram analysis.
_Avoid_: Test, Chunk, Segment

**Event**:
A single logged keystroke (timestamp, key, correctness class) — the raw unit captured by the keylogger within a Session.
_Avoid_: Keystroke (fine in prose, but Event is the schema term)

**Bigram Latency**:
The time between two consecutive single-character Events, used as a proxy for how slow that two-key sequence is for the typist.
_Avoid_: Gap, interval
