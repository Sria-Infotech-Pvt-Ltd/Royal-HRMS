"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import {
  DEFAULT_THEME, applyTheme, isThemeAccent, isThemeMode, normaliseTheme, readStoredTheme, storeTheme, watchDeviceMode,
  type ThemeChoice,
} from "@/lib/theme";

interface SavedTheme { mode: string | null; accent: string | null }

/** The signed-in person's theme. Applies it to the page, remembers it in the browser, and saves it on their profile. */
export function useTheme(): { theme: ThemeChoice; choose: (change: Partial<ThemeChoice>) => void } {
  const [theme, setTheme] = useState<ThemeChoice>(DEFAULT_THEME);
  const { data: saved } = useFetch<SavedTheme>(API.employees.myTheme);

  // First render matches the server (default); then the browser's choice, which the boot script in <head> already painted.
  useEffect(() => {
    const stored = readStoredTheme();
    setTheme(stored);
    applyTheme(stored);
  }, []);

  // What is saved on the profile wins, so the choice follows the person to another device.
  useEffect(() => {
    if (!saved || !isThemeMode(saved.mode) || !isThemeAccent(saved.accent)) return;
    const fromProfile = normaliseTheme(saved);
    setTheme(fromProfile);
    applyTheme(fromProfile);
    storeTheme(fromProfile);
  }, [saved]);

  // "Match my device" follows the device when it switches between light and dark.
  useEffect(() => {
    if (theme.mode !== "system") return undefined;
    return watchDeviceMode(() => applyTheme(theme));
  }, [theme]);

  const choose = useCallback((change: Partial<ThemeChoice>) => {
    const next = { ...theme, ...change };
    setTheme(next);
    applyTheme(next);
    storeTheme(next);
    // The choice already applies on this device; a failed save only means it will not follow to another one.
    clientApi.put(API.employees.myTheme, next).catch(() => undefined);
  }, [theme]);

  return { theme, choose };
}
