// ==UserScript==
// @name         Monkeytype Keystroke Logger
// @namespace    typing-research
// @version      3.3
// @description  Logs per-keystroke timestamps and the active test config on Monkeytype, periodically saved as session files into Downloads, for bigram-latency analysis the public API doesn't expose.
// @match        https://monkeytype.com/*
// @grant        GM_download
// ==/UserScript==

// Sessions land in <Downloads>/monkeytype-keylogs/<date>/<session>-part<N>.json:
// one file per periodic save (every 3 min by default) plus a best-effort
// final save when the tab closes. Only runs on monkeytype.com, per @match
// above. Periodically move/clean up that folder into
// ~/dev/monkeytype_tools/data/keylogs/ (analyze_keylog.py scans there by
// default), e.g.:
//   mv ~/Downloads/monkeytype-keylogs/* ~/dev/monkeytype_tools/data/keylogs/
// Ctrl+Shift+E forces an immediate save too.
//
// Each saved file also carries a `config` snapshot (Monkeytype's own
// localStorage settings: mode, word/time target, punctuation, numbers,
// difficulty, layout, funbox, ...) as of that save, so keystroke data can
// later be segmented by what test/settings it was actually typed under.

(function () {
  "use strict";

  const FLUSH_INTERVAL_MS = 3 * 60 * 1000;
  const DOWNLOAD_SUBFOLDER = "monkeytype-keylogs";
  const sessionId = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  let pending = [];
  let partIndex = 0;

  function lastResolvedLetterClasses() {
    // Best-effort correctness signal, verified live against monkeytype.com:
    // there is no per-letter "active" class (that's on the .word div only).
    // Typed letters get class "correct" or "incorrect" on the <letter>
    // element, so the most recently resolved one in the active word is
    // what we just typed. If this stops matching (site markup changed),
    // classes will just come back empty. Check with devtools on #words.
    const activeWord = document.querySelector("#words .word.active");
    if (!activeWord) return [];
    const resolved = activeWord.querySelectorAll("letter.correct, letter.incorrect");
    if (resolved.length === 0) return [];
    return Array.from(resolved[resolved.length - 1].classList).filter(Boolean);
  }

  document.addEventListener(
    "keydown",
    (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === "E") return; // the export hotkey itself, not typing content
      // OS key-repeat firing while a key is held down. Monkeytype's own input
      // handling ignores these (e.g. holding space past the end of a word does
      // nothing once the next word is empty), so logging them fabricates
      // keystrokes/bigrams that never became part of any result. Confirmed
      // against typing.duckdb: every double-space bigram in the data had zero
      // resolved letters on the second keydown; it never advanced the test.
      if (e.repeat) return;
      if (e.key.length > 1 && e.key !== "Backspace" && e.key !== " ") return;
      // Only log keys typed into the actual test input while a test is
      // actively being typed - not keys typed elsewhere on the page
      // (leaderboard search, settings, account/profile fields, ...) and not
      // idle focus on #wordsInput with no test running (start screen,
      // between quick-restarts, results screen). Fails closed on both
      // checks: if #wordsInput or the active word can't be found (site
      // markup changed, or we're simply on a different monkeytype.com route
      // that doesn't have a test screen at all - @match is the whole site),
      // drop the event instead of logging it. A gap in the data is visible
      // and harmless; a phantom bigram from leaked keystrokes silently
      // corrupts stats. Confirmed against typing.duckdb: before this check
      // existed, ~25% of "attempts" never matched any real test result, and
      // averaged ~34 events vs. ~414 for real ones - stray typing bleeding
      // into bigram/key stats as if it were test content.
      const wordsInput = document.getElementById("wordsInput");
      if (document.activeElement !== wordsInput) return;
      if (!document.querySelector("#words .word.active")) return;
      const ts = Date.now();
      const key = e.key;
      // deferred to macrotask: our listener is capture-phase on document,
      // which fires before Monkeytype's own handler (bound on #wordsInput)
      // resolves the correct/incorrect class for this keystroke
      setTimeout(() => pending.push({ ts, key, classes: lastResolvedLetterClasses() }), 0);
    },
    true
  );

  function isoDate(d) {
    return d.toISOString().slice(0, 10);
  }

  function currentConfig() {
    // Monkeytype persists the full active test config to localStorage as
    // plain JSON (mode, word/time target, punctuation, numbers, difficulty,
    // stopOnError, freedomMode, blindMode, funbox, layout, ...). Read fresh
    // at save time so each part reflects whatever was active as of that
    // save, not whatever was active on page load. If the user changes
    // settings mid-buffer without triggering a save, events in that part
    // may span the change unnoticed; it's not tracked at finer granularity.
    try {
      const raw = localStorage.getItem("config");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function saveSession() {
    if (pending.length === 0) return;
    const toSave = pending;
    pending = [];
    partIndex += 1;

    const now = new Date();
    const envelope = {
      schema_version: 2,
      source: "monkeytype-keylogger",
      session_id: sessionId,
      part: partIndex,
      url: location.href,
      saved_at: now.toISOString(),
      config: currentConfig(),
      events: toSave,
    };

    const blob = new Blob([JSON.stringify(envelope)], { type: "application/json" });
    const blobUrl = URL.createObjectURL(blob);
    const filename = `${DOWNLOAD_SUBFOLDER}/${isoDate(now)}/${sessionId}-part${partIndex}.json`;

    GM_download({
      url: blobUrl,
      name: filename,
      saveAs: false,
      onload: () => URL.revokeObjectURL(blobUrl),
      onerror: (err) => {
        console.warn("[mt-logger] GM_download failed, re-queueing", err);
        pending = toSave.concat(pending);
        partIndex -= 1;
        URL.revokeObjectURL(blobUrl);
      },
    });
  }

  setInterval(saveSession, FLUSH_INTERVAL_MS);

  // Best-effort final save on tab close. Not guaranteed to finish since the
  // page is tearing down, but GM_download hands off to the browser's own
  // download manager rather than a page-level network request, so it
  // survives teardown more often than fetch/XHR would. pagehide fires more
  // reliably than beforeunload for this.
  window.addEventListener("pagehide", saveSession);

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === "E") {
      e.preventDefault();
      saveSession();
      console.log("[mt-logger] manual session save triggered");
    }
  });

  console.log(
    `[mt-logger] loaded, session ${sessionId}. Auto-saving every ${FLUSH_INTERVAL_MS / 60000} min to Downloads/${DOWNLOAD_SUBFOLDER}/.`
  );
})();
