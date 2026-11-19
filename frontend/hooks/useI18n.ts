"use client";

import { createContext, useContext } from "react";
import { DEFAULT_LANGUAGE, type LanguageCode } from "@/lib/i18n/languages";
import { translate, type TranslateParams } from "@/lib/i18n/translate";

export interface I18n {
  language: LanguageCode;
  /** Changes the language for this browser. Saving it on the person's profile is done by the language picker. */
  setLanguage: (language: LanguageCode) => void;
  /** The wording for an English text in the current language; the English text itself when there is no translation yet. */
  t: (text: string, params?: TranslateParams) => string;
}

// Without a provider (tests, or a page outside the app shell) everything simply reads in English.
export const I18nContext = createContext<I18n>({
  language: DEFAULT_LANGUAGE,
  setLanguage: () => undefined,
  t: (text, params) => translate(DEFAULT_LANGUAGE, text, params),
});

export function useI18n(): I18n {
  return useContext(I18nContext);
}

/** Shortcut for screens that only need to translate: `const t = useT();` */
export function useT(): I18n["t"] {
  return useContext(I18nContext).t;
}
