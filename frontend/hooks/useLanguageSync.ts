"use client";

import { useCallback, useEffect } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useI18n } from "@/hooks/useI18n";
import { isLanguageCode, type LanguageCode } from "@/lib/i18n/languages";

interface SavedLanguage { language: string | null }

/** For signed-in screens: the profile's language wins on load (so it follows the person to another device), and a change is saved back. */
export function useLanguageSync(): { language: LanguageCode; choose: (language: LanguageCode) => void } {
  const { language, setLanguage } = useI18n();
  const { data: saved } = useFetch<SavedLanguage>(API.employees.myLanguage);

  useEffect(() => {
    if (saved && isLanguageCode(saved.language)) setLanguage(saved.language);
  }, [saved, setLanguage]);

  const choose = useCallback((next: LanguageCode) => {
    setLanguage(next);
    // The language already applies on this device; a failed save only means it will not follow to another one.
    clientApi.put(API.employees.myLanguage, { language: next }).catch(() => undefined);
  }, [setLanguage]);

  return { language, choose };
}
