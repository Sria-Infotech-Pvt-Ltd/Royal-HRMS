"use client";

import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { I18nContext, type I18n } from "@/hooks/useI18n";
import { DEFAULT_LANGUAGE, readStoredLanguage, storeLanguage, type LanguageCode } from "@/lib/i18n/languages";
import { setActiveLanguage } from "@/lib/i18n/tr";
import { translate } from "@/lib/i18n/translate";

/** Holds the chosen language for the whole app. The first render is English on the server and the client alike; the saved choice is read right after. */
export default function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>(DEFAULT_LANGUAGE);

  useEffect(() => {
    setLanguageState(readStoredLanguage());
  }, []);

  // Screen readers and browser translation tools read this.
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((next: LanguageCode) => {
    setLanguageState(next);
    storeLanguage(next);
  }, []);

  const value = useMemo<I18n>(
    () => ({ language, setLanguage, t: (text, params) => translate(language, text, params) }),
    [language, setLanguage],
  );

  // Set during render, before the children render, so every tr(...) below already sees the new language.
  setActiveLanguage(language);

  // Changing the language remounts the app below (key), so that screens using the plain tr() function, which do not subscribe to this
  // context, are evaluated again. It happens only when the language changes. GETs still in flight are shared (see useFetch), so the
  // remount right after the first page load does not repeat requests.
  return <I18nContext.Provider value={value}><Fragment key={language}>{children}</Fragment></I18nContext.Provider>;
}
