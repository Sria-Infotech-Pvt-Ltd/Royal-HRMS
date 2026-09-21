"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "aira-dark-mode";

// The app's dark palette already exists as CSS variables under
// `html[data-theme="dark"]` (app/globals.css) — this is the only place
// anything actually sets that attribute, and it persists the choice so it
// survives a reload/new tab.
export default function DarkModeToggle() {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) === "1";
    setIsDark(stored);
    document.documentElement.dataset.theme = stored ? "dark" : "light";
    setMounted(true);
  }, []);

  function toggle() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
  }

  return (
    <button
      className="iconbtn"
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
      suppressHydrationWarning
    >
      <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        {mounted && isDark
          ? <><circle cx="12" cy="12" r="4.5" /><path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" /></>
          : <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />}
      </svg>
    </button>
  );
}
