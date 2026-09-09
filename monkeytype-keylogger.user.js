// ==UserScript==
// @name         Monkeytype Keystroke Logger
// @namespace    typing-research
// @version      3.7
// @description  Logs per-keystroke timestamps and the active test config on Monkeytype, periodically saved as session files into Downloads, for bigram-latency analysis the public API doesn't expose. Also fetches generated drills from the local dashboard backend, loads them into Monkeytype's custom-text mode, and tags completions for closed-loop validation.
// @match        https://monkeytype.com/*
// @grant        GM_download
// ==/UserScript==

(function () {
  "use strict";

  const FLUSH_INTERVAL_MS = 3 * 60 * 1000;
  const MIN_FLUSH_GAP_MS = 5 * 1000;

  const SNAPSHOT_KEY = "mt-logger-snapshot";
  const SNAPSHOT_EVERY_N = 20;
  const SNAPSHOT_EVERY_MS = 5 * 1000;
  const DOWNLOAD_SUBFOLDER = "monkeytype-keylogs";
  const sessionId = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  let pending = [];
  let partIndex = 0;
  let lastFlushAt = 0;
  let lastSnapshotAt = 0;
  let eventsSinceSnapshot = 0;

  function lastResolvedLetterClasses() {
    const activeWord = document.querySelector("#words .word.active");
    if (!activeWord) return [];
    const resolved = activeWord.querySelectorAll("letter.correct, letter.incorrect");
    if (resolved.length === 0) return [];
    return Array.from(resolved[resolved.length - 1].classList).filter(Boolean);
  }

  document.addEventListener(
    "keydown",
    (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === "E") return;
      if (e.repeat) return;
      if (e.key.length > 1 && e.key !== "Backspace" && e.key !== " ") return;

      const wordsInput = document.getElementById("wordsInput");
      if (document.activeElement !== wordsInput) return;
      if (!document.querySelector("#words .word.active")) return;
      const ts = Date.now();
      const key = e.key;

      setTimeout(() => {
        pending.push({ ts, key, classes: lastResolvedLetterClasses() });
        maybeSnapshot();
      }, 0);
    },
    true
  );

  function isoDate(d) {
    return d.toISOString().slice(0, 10);
  }

  function currentConfig() {
    try {
      const raw = localStorage.getItem("config");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function buildEnvelope(events, part) {
    return {
      schema_version: 3,
      source: "monkeytype-keylogger",
      session_id: sessionId,
      part,
      url: location.href,
      saved_at: new Date().toISOString(),
      config: currentConfig(),
      drill: pendingDrill,
      events,
    };
  }

  function downloadEnvelope(envelope, { recovered = false, onFail } = {}) {
    const blob = new Blob([JSON.stringify(envelope)], { type: "application/json" });
    const blobUrl = URL.createObjectURL(blob);
    const suffix = recovered ? "-recovered" : "";
    const filename = `${DOWNLOAD_SUBFOLDER}/${isoDate(new Date(envelope.saved_at))}/${envelope.session_id}-part${envelope.part}${suffix}.json`;

    GM_download({
      url: blobUrl,
      name: filename,
      saveAs: false,
      onload: () => URL.revokeObjectURL(blobUrl),
      onerror: (err) => {
        console.warn("[mt-logger] GM_download failed", err);
        if (onFail) onFail();
        URL.revokeObjectURL(blobUrl);
      },
    });
  }

  function clearSnapshot() {
    try {
      localStorage.removeItem(SNAPSHOT_KEY);
    } catch (e) {
      // ignore
    }
  }

  function writeSnapshot() {
    eventsSinceSnapshot = 0;
    lastSnapshotAt = Date.now();
    try {
      localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(buildEnvelope(pending, partIndex + 1)));
    } catch (e) {
      console.warn("[mt-logger] snapshot write failed", e);
    }
  }

  function maybeSnapshot() {
    eventsSinceSnapshot += 1;
    if (eventsSinceSnapshot >= SNAPSHOT_EVERY_N || Date.now() - lastSnapshotAt >= SNAPSHOT_EVERY_MS) {
      writeSnapshot();
    }
  }

  function recoverSnapshot() {
    let raw;
    try {
      raw = localStorage.getItem(SNAPSHOT_KEY);
    } catch (e) {
      return;
    }
    if (!raw) return;
    clearSnapshot();
    try {
      const snap = JSON.parse(raw);
      if (snap.events && snap.events.length > 0) {
        downloadEnvelope(snap, { recovered: true });
        console.warn(`[mt-logger] recovered ${snap.events.length} events from an unclean previous session`);
      }
    } catch (e) {
      console.warn("[mt-logger] snapshot recovery failed to parse", e);
    }
  }

  recoverSnapshot();

  function saveSession() {
    if (pending.length === 0) return;
    const toSave = pending;
    pending = [];
    partIndex += 1;
    lastFlushAt = Date.now();
    eventsSinceSnapshot = 0;
    lastSnapshotAt = lastFlushAt;
    clearSnapshot();

    const envelope = buildEnvelope(toSave, partIndex);
    downloadEnvelope(envelope, {
      onFail: () => {
        pending = toSave.concat(pending);
        partIndex -= 1;
      },
    });
  }

  function throttledSave() {
    if (Date.now() - lastFlushAt < MIN_FLUSH_GAP_MS) return;
    saveSession();
  }

  setInterval(saveSession, FLUSH_INTERVAL_MS);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") throttledSave();
  });

  window.addEventListener("pagehide", saveSession);

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === "E") {
      e.preventDefault();
      saveSession();
      console.log("[mt-logger] manual session save triggered");
    }
  });

  const BACKEND_BASE = "http://127.0.0.1:8000";
  const PENDING_DRILL_KEY = "mt-logger-pending-drill";

  const DRILL_TAG_OVERRIDES = { awkward_roll: "drill-roll" };

  function tagNameForCategory(key) {
    return DRILL_TAG_OVERRIDES[key] || `drill-${key}`;
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
    const res = await fetch(`${BACKEND_BASE}/api/drill-manifest`);
    if (!res.ok) throw new Error(`drill-manifest fetch failed: ${res.status}`);
    const data = await res.json();
    return categoryKey === "overall"
      ? data.overall
      : (data.categories || []).find((c) => c.key === categoryKey) || null;
  }

  function findButtonByText(text, root = document) {
    const normalized = text.trim().toLowerCase();
    for (const el of root.querySelectorAll("button")) {
      if (el.textContent && el.textContent.trim().toLowerCase() === normalized) return el;
    }
    return null;
  }

  function fillCustomTextForm(text) {
    const textarea = document.querySelector("textarea#text");
    if (!textarea) return false;
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setValue.call(textarea, text);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));

    const form = textarea.closest("form");
    const okButton = (form && form.querySelector('button[type="submit"]')) || findButtonByText("ok");
    if (!okButton) return false;
    okButton.click();
    return true;
  }

  function openCustomTextPopupAndFill(text, attempt = 0) {
    if (fillCustomTextForm(text)) return;

    const customModeBtn = findButtonByText("custom");
    if (customModeBtn) customModeBtn.click();

    setTimeout(() => {
      if (fillCustomTextForm(text)) return;
      const changeBtn = findButtonByText("change");
      if (changeBtn) {
        changeBtn.click();
        setTimeout(() => {
          if (!fillCustomTextForm(text)) {
            console.warn('[mt-logger] found "change" but could not fill the popup - check fillCustomTextForm() selectors live');
          }
        }, 200);
      } else if (attempt < 1) {
        setTimeout(() => openCustomTextPopupAndFill(text, attempt + 1), 300);
      } else {
        console.warn('[mt-logger] could not find "custom" mode or "change" button - open custom mode manually once, then retry');
      }
    }, 200);
  }

  function applyDrill(manifest) {
    if (!manifest || !manifest.text) {
      console.warn("[mt-logger] no drill available for", manifest && manifest.key);
      return;
    }
    const text = manifest.text;

    pendingDrill = {
      category: manifest.key,
      label: manifest.label,
      bigrams: manifest.bigrams,
      generated_at: manifest.generated_at,
      applied_at: new Date().toISOString(),
    };
    sessionStorage.setItem(PENDING_DRILL_KEY, JSON.stringify(pendingDrill));
    openCustomTextPopupAndFill(text);
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

  function findTagPopup() {
    for (const modal of document.querySelectorAll(".modal")) {
      if (modal.textContent.includes("Edit result tags")) return modal;
    }
    return null;
  }

  function findTagToggle(popup, tagName) {
    const normalize = (s) => s.trim().toLowerCase().replace(/_/g, " ");
    const target = normalize(tagName);
    for (const btn of popup.querySelectorAll("button")) {
      if (normalize(btn.textContent || "") === target) return btn;
    }
    return null;
  }

  function tryApplyPendingTag(editTagsButton) {
    if (!pendingDrill) return;
    const tagName = tagNameForCategory(pendingDrill.category);
    editTagsButton.click();
    setTimeout(() => {
      const popup = findTagPopup();
      if (!popup) {
        console.warn("[mt-logger] tag popup did not open (no .modal containing \"Edit result tags\" found)");
        clearPendingDrill();
        return;
      }
      const toggle = findTagToggle(popup, tagName);
      if (!toggle) {
        console.warn(
          `[mt-logger] could not find tag "${tagName}" in the tag editor - ` +
          "create it once in Monkeytype's UI (Account > tags) if it doesn't exist yet"
        );
        clearPendingDrill();
        return;
      }
      toggle.click();
      const saveBtn = findButtonByText("save", popup);
      if (saveBtn) {
        saveBtn.click();
        console.log(`[mt-logger] applied tag "${tagName}" to completed drill`);
      } else {
        console.warn(`[mt-logger] toggled "${tagName}" but could not find the popup's "save" button - not persisted`);
      }
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
