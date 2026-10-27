"use client";

// Which top-bar menu is open (at most one). Click opens/closes it; while one is open, pointing at another switches
// to it; Escape, a click outside any menu, or leaving the page closes it.

import { useCallback, useEffect, useState } from "react";

/** Put this attribute on every element that belongs to a menu (trigger and panel) so clicks inside don't close it. */
export const MENU_ATTRIBUTE = "data-nav-menu";

export interface OpenMenu {
  openKey: string | null;
  toggle: (key: string) => void;
  /** Switch to `key` only if some menu is already open. */
  switchTo: (key: string) => void;
  close: () => void;
}

export function useOpenMenu(pathname: string): OpenMenu {
  const [openKey, setOpenKey] = useState<string | null>(null);

  const close = useCallback(() => setOpenKey(null), []);
  const toggle = useCallback((key: string) => setOpenKey(current => (current === key ? null : key)), []);
  const switchTo = useCallback((key: string) => setOpenKey(current => (current === null ? current : key)), []);

  useEffect(() => { setOpenKey(null); }, [pathname]);

  useEffect(() => {
    if (openKey === null) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenKey(null);
    }
    function onPointerDown(event: MouseEvent) {
      if (!(event.target instanceof Element) || !event.target.closest(`[${MENU_ATTRIBUTE}]`)) setOpenKey(null);
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [openKey]);

  return { openKey, toggle, switchTo, close };
}
