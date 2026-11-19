// The languages the screens can be shown in. English is the source: every screen's text is written in English in the code, and a
// language file maps that English text to its own wording (see translate.ts). Keep in step with LANGUAGE_CODES in
// backend/apps/accounts/views_language.py.

export const LANGUAGES = ["en", "hi", "te"] as const;
export type LanguageCode = (typeof LANGUAGES)[number];

export const DEFAULT_LANGUAGE: LanguageCode = "en";
export const LANGUAGE_STORAGE_KEY = "aira-language";

/** Each language is named in its own script, so a person can find theirs even when the screen is in a language they cannot read. */
export const LANGUAGE_NAMES: Record<LanguageCode, string> = { en: "English", hi: "हिन्दी", te: "తెలుగు" };

export function isLanguageCode(value: unknown): value is LanguageCode {
  return typeof value === "string" && (LANGUAGES as readonly string[]).includes(value);
}

export function readStoredLanguage(): LanguageCode {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLanguageCode(stored)) return stored;
  } catch {
    // Storage blocked: use the default.
  }
  return DEFAULT_LANGUAGE;
}

export function storeLanguage(language: LanguageCode): void {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Storage blocked: the choice still applies for this page view.
  }
}
