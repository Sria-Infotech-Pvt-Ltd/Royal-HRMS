"use client";

// Keyboard behaviour every dialog needs: focus moves into it when it opens, Tab stays inside it, Esc closes it, and focus goes
// back to whatever opened it when it closes.

import { useEffect, type RefObject } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Open dialogs, outermost first: a dialog opened over another (a confirmation over a form) is on top and alone handles Esc and Tab.
const openDialogs: HTMLElement[] = [];

export function useDialogFocus(dialogRef: RefObject<HTMLElement | null>, onEscape: (() => void) | null): void {
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    openDialogs.push(dialog);

    // Focus the first control, or the dialog itself when it has none; leave it alone if something inside already took focus.
    if (!dialog.contains(document.activeElement)) {
      const first = dialog.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? dialog).focus({ preventScroll: true });
    }

    function onKeyDown(event: KeyboardEvent) {
      if (openDialogs[openDialogs.length - 1] !== dialog) return;
      if (event.key === "Escape" && onEscape) {
        event.stopPropagation();
        onEscape();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(item => item.offsetParent !== null);
      if (items.length === 0) { event.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialog.contains(active))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (active === last || !dialog.contains(active))) { event.preventDefault(); first.focus(); }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      openDialogs.splice(openDialogs.indexOf(dialog), 1);
      if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    };
    // Runs once per open: the dialog element and the opener are fixed for its lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
