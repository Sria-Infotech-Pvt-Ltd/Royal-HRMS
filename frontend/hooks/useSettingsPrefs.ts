"use client";

// Per-person conveniences for the Settings landing page: which settings are pinned, and grid or list view.
// Kept in this browser only (nothing sensitive, and the page works without it), read after the first render so the server and the
// browser agree on what is drawn first.

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "aira_settings_prefs";

export type SettingsLayout = "grid" | "list";

interface Prefs { pinned: string[]; layout: SettingsLayout }
const EMPTY: Prefs = { pinned: [], layout: "grid" };

const isTextList = (value: unknown): value is string[] => Array.isArray(value) && value.every(entry => typeof entry === "string");

function readPrefs(): Prefs {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null");
    if (typeof parsed !== "object" || parsed === null) return EMPTY;
    const { pinned, layout } = parsed as Record<string, unknown>;
    return { pinned: isTextList(pinned) ? pinned : [], layout: layout === "list" ? "list" : "grid" };
  } catch {
    return EMPTY;
  }
}

function writePrefs(prefs: Prefs) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Private window or blocked storage: the choices simply last until the page is closed.
  }
}

export function useSettingsPrefs() {
  const [prefs, setPrefs] = useState<Prefs>(EMPTY);

  useEffect(() => { setPrefs(readPrefs()); }, []);

  const update = useCallback((change: (previous: Prefs) => Prefs) => {
    setPrefs(previous => {
      const next = change(previous);
      writePrefs(next);
      return next;
    });
  }, []);

  const togglePinned = useCallback((id: string) => update(previous => ({ ...previous, pinned: previous.pinned.includes(id) ? previous.pinned.filter(entry => entry !== id) : [...previous.pinned, id] })), [update]);
  const setLayout = useCallback((layout: SettingsLayout) => update(previous => ({ ...previous, layout })), [update]);

  return { pinned: prefs.pinned, layout: prefs.layout, togglePinned, setLayout };
}
