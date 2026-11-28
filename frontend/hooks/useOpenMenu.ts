"use client";

// Which top-bar menu is open (at most one). With a mouse, pointing at a menu opens it and moving away closes it after a
// short pause (so the pointer can cross the gap into the panel). On touch screens and from the keyboard a click opens and
// closes it. While one is open, pointing at another switches to it; Escape, a click outside any menu, or leaving the page
// closes it.

import { useCallback, useEffect, useRef, useState } from "react";

/** Put this attribute on every element that belongs to a menu (trigger and panel) so clicks inside don't close it. */
export const MENU_ATTRIBUTE = "data-nav-menu";

export interface OpenMenu {
  openKey: string | null;
  toggle: (key: string) => void;
  /** Switch to `key` only if some menu is already open. */
  switchTo: (key: string) => void;
  /** The pointer entered menu `key`: opens it on a device that can hover. */
  hoverOpen: (key: string) => void;
  /** The pointer left the menu: closes it after a short pause, unless it comes back. */
  hoverLeave: () => void;
  /** The trigger was clicked. With a mouse this only opens (hover already did); from a keyboard or touch it toggles. */
  press: (key: string, isFromKeyboard: boolean) => void;
  close: () => void;
}

// Long enough to cross the few pixels between a trigger and its panel, short enough to feel immediate.
const HOVER_CLOSE_DELAY_MS = 200;

/** True on a device with a real hovering pointer (a mouse or trackpad), not a touch screen. */
function canHover(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;
}

export function useOpenMenu(pathname: string): OpenMenu {
  const [openKey, setOpenKey] = useState<string | null>(null);

  const close = useCallback(() => setOpenKey(null), []);
  const toggle = useCallback((key: string) => setOpenKey(current => (current === key ? null : key)), []);
  const switchTo = useCallback((key: string) => setOpenKey(current => (current === null ? current : key)), []);

  const closeTimer = useRef<number | null>(null);
  const cancelPendingClose = useCallback(() => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);
  const hoverOpen = useCallback((key: string) => {
    if (!canHover()) return;
    cancelPendingClose();
    setOpenKey(key);
  }, [cancelPendingClose]);
  const hoverLeave = useCallback(() => {
    if (!canHover()) return;
    cancelPendingClose();
    closeTimer.current = window.setTimeout(() => { closeTimer.current = null; setOpenKey(null); }, HOVER_CLOSE_DELAY_MS);
  }, [cancelPendingClose]);
  const press = useCallback((key: string, isFromKeyboard: boolean) => {
    cancelPendingClose();
    if (canHover() && !isFromKeyboard) setOpenKey(key);
    else toggle(key);
  }, [cancelPendingClose, toggle]);
  useEffect(() => cancelPendingClose, [cancelPendingClose]);

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

  return { openKey, toggle, switchTo, hoverOpen, hoverLeave, press, close };
}
