// ==UserScript==
// @name         Monkeytype Keystroke Logger
// @namespace    typing-research
// @version      3.4
// @description  Logs per-keystroke timestamps and the active test config on Monkeytype, periodically saved as session files into Downloads, for bigram-latency analysis the public API doesn't expose. Also fetches generated drills from the local dashboard backend, loads them into Monkeytype's custom-text mode, and tags completions for closed-loop validation.
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
//
// A small button panel (bottom-right) fetches the most recently generated
// drill from the local dashboard backend (127.0.0.1:8000) per
// docs/adr/0003-drill-completion-validation.md, and loads it into
// Monkeytype's own custom-text storage. If a drill is pending when a
// custom test completes, the saved envelope's `drill` field records exactly
// which bigrams were targeted (the drill files themselves regenerate from
// live data on every dashboard load, so that can't be re-derived later from
// whatever's currently on disk), and the script attempts to tag the result
// with `drill-<category>` so later analysis can tell a genuine drill
// completion apart from any other typing. Tags must already exist in
// Monkeytype (created once, by hand) before this can find them by name.

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
      schema_version: 3,
      source: "monkeytype-keylogger",
      session_id: sessionId,
      part: partIndex,
      url: location.href,
      saved_at: now.toISOString(),
      config: currentConfig(),
      // Which drill (if any) was loaded for this session, per
      // docs/adr/0003-drill-completion-validation.md - null once no drill is
      // pending (never applied, or already resolved after a completion).
      drill: pendingDrill,
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

  // --- Drill automation (docs/adr/0003-drill-completion-validation.md) ---
  //
  // NOTE: the localStorage schema below (customText / customTextSettings)
  // and the tag-editor popup's internal structure were reverse-engineered
  // from Monkeytype's live bundle, not confirmed by actually driving the UI
  // end-to-end from here. Treat applyDrill()'s "does this actually start a
  // custom test on reload" and findTagToggle()'s selector as best-effort -
  // verify against the live site and adjust if either stops working, the
  // same way lastResolvedLetterClasses() above is already flagged.

  const BACKEND_BASE = "http://127.0.0.1:8000";
  const PENDING_DRILL_KEY = "mt-logger-pending-drill";
  const DRILL_TEXT_NAME = "__drill_active__"; // fixed slot in Monkeytype's own customText map - overwritten every time, not a saved preset (0003)

  function tagNameForCategory(key) {
    return `drill-${key}`;
  }

  function loadPendingDrill() {
    try {
      const raw = sessionStorage.getItem(PENDING_DRILL_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  let pendingDrill = loadPendingDrill();

  function clearPendingDrill() {
    pendingDrill = null;
    sessionStorage.removeItem(PENDING_DRILL_KEY);
  }

  async function fetchDrillManifest(categoryKey) {
    // Plain fetch, not GM_xmlhttpRequest: server.py already sends wildcard
    // CORS on GET routes, so no cross-origin grant is needed for reads.
    const res = await fetch(`${BACKEND_BASE}/api/drill-manifest`);
    if (!res.ok) throw new Error(`drill-manifest fetch failed: ${res.status}`);
    const data = await res.json();
    return categoryKey === "overall"
      ? data.overall
      : (data.categories || []).find((c) => c.key === categoryKey) || null;
  }

  function applyDrill(manifest) {
    if (!manifest || !manifest.text) {
      console.warn("[mt-logger] no drill available for", manifest && manifest.key);
      return;
    }
    const words = manifest.text.split("|");

    let customText = {};
    try {
      customText = JSON.parse(localStorage.getItem("customText") || "{}");
    } catch (e) {
      /* fall through with empty map */
    }
    customText[DRILL_TEXT_NAME] = words.join(" ");
    localStorage.setItem("customText", JSON.stringify(customText));

    let customTextSettings = { mode: "word", pipeDelimiter: true, limit: { mode: "word", value: words.length } };
    try {
      customTextSettings = {
        ...customTextSettings,
        ...JSON.parse(localStorage.getItem("customTextSettings") || "{}"),
      };
    } catch (e) {
      /* fall through with the default above */
    }
    customTextSettings.pipeDelimiter = true; // required for drill_practice*.txt's "|" grouping to parse as intended
    localStorage.setItem("customTextSettings", JSON.stringify(customTextSettings));

    try {
      const config = JSON.parse(localStorage.getItem("config") || "{}");
      config.mode = "custom";
      localStorage.setItem("config", JSON.stringify(config));
    } catch (e) {
      /* if this fails, mode will just need picking manually after reload */
    }

    pendingDrill = {
      category: manifest.key,
      label: manifest.label,
      bigrams: manifest.bigrams,
      generated_at: manifest.generated_at,
      applied_at: new Date().toISOString(),
    };
    sessionStorage.setItem(PENDING_DRILL_KEY, JSON.stringify(pendingDrill));
    location.reload();
  }

  function injectDrillPanel() {
    if (!document.body || document.getElementById("mt-logger-drill-panel")) return;
    const panel = document.createElement("div");
    panel.id = "mt-logger-drill-panel";
    panel.style.cssText =
      "position:fixed;bottom:8px;right:8px;z-index:9999;display:flex;gap:4px;" +
      "background:rgba(0,0,0,.6);padding:6px;border-radius:6px;font:11px sans-serif;";

    const categories = [
      ["overall", "Overall"],
      ["sfb", "SFB"],
      ["row_skip", "Row-skip"],
      ["awkward_roll", "Awkward"],
      ["lsb", "LSB"],
    ];
    for (const [key, label] of categories) {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.style.cssText = "cursor:pointer;padding:4px 6px;";
      btn.addEventListener("click", async () => {
        try {
          applyDrill(await fetchDrillManifest(key));
        } catch (e) {
          console.warn("[mt-logger] drill fetch/apply failed", e);
        }
      });
      panel.appendChild(btn);
    }
    document.body.appendChild(panel);
  }

  function findTagToggle(tagName) {
    // Unverified: only the editTagsButton itself (with its data-result-id /
    // data-active-tag-ids attributes) was confirmed against the live site.
    // The popup this opens was not inspected live, so this falls back to a
    // generic text-match rather than a guessed class name - find a
    // clickable element whose own text is exactly the tag's display name
    // (Monkeytype turns spaces into underscores in tag names). Adjust this
    // against the live popup if it keeps missing.
    const candidates = document.querySelectorAll("button, .tag, [class*='tag']");
    for (const el of candidates) {
      if (el.textContent && el.textContent.trim() === tagName) return el;
    }
    return null;
  }

  function tryApplyPendingTag(editTagsButton) {
    if (!pendingDrill) return;
    const tagName = tagNameForCategory(pendingDrill.category);
    editTagsButton.click();
    // Popup rendering is async; give it a beat before searching for the tag.
    setTimeout(() => {
      const toggle = findTagToggle(tagName);
      if (toggle) {
        toggle.click();
        console.log(`[mt-logger] applied tag "${tagName}" to completed drill`);
      } else {
        console.warn(
          `[mt-logger] could not find tag "${tagName}" in the tag editor - ` +
            "create it once in Monkeytype's UI (Account > tags), and check " +
            "findTagToggle()'s selector against the live popup if this keeps failing"
        );
      }
      document.body.click(); // best-effort: close the popup
      clearPendingDrill();
    }, 300);
  }

  function watchForCompletion() {
    const observer = new MutationObserver(() => {
      if (!pendingDrill) return;
      const btn = document.querySelector("#result .stats .tags .editTagsButton");
      if (btn && btn.getAttribute("data-result-id")) {
        tryApplyPendingTag(btn);
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-result-id"],
    });
  }

  if (document.body) {
    injectDrillPanel();
  } else {
    document.addEventListener("DOMContentLoaded", injectDrillPanel);
  }
  watchForCompletion();

  console.log(
    `[mt-logger] loaded, session ${sessionId}. Auto-saving every ${FLUSH_INTERVAL_MS / 60000} min to Downloads/${DOWNLOAD_SUBFOLDER}/.`
  );
})();
