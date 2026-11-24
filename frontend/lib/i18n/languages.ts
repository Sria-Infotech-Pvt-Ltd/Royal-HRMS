// The languages the screens can be shown in. English is the source: every screen's text is written in English in the code, and a
// language file maps that English text to its own wording (see translate.ts). Keep in step with LANGUAGE_CODES in
// backend/apps/accounts/views_language.py.

// English first, then the languages by how many people in India speak them.
export const LANGUAGES = ["en", "hi", "bn", "mr", "te", "ta", "gu", "ur", "kn", "or", "ml", "pa", "as"] as const;
export type LanguageCode = (typeof LANGUAGES)[number];

export const DEFAULT_LANGUAGE: LanguageCode = "en";
export const LANGUAGE_STORAGE_KEY = "aira-language";

/** Each language is named in its own script, so a person can find theirs even when the screen is in a language they cannot read. */
export const LANGUAGE_NAMES: Record<LanguageCode, string> = {
  en: "English", hi: "हिन्दी", bn: "বাংলা", mr: "मराठी", te: "తెలుగు", ta: "தமிழ்", gu: "ગુજરાતી", ur: "اردو", kn: "ಕನ್ನಡ", or: "ଓଡ଼ିଆ",
  ml: "മലയാളം", pa: "ਪੰਜਾਬੀ", as: "অসমীয়া",
};

/** The same names in English, shown small under the native name so a person can tell which is which when the script is unfamiliar. */
export const LANGUAGE_ENGLISH_NAMES: Record<LanguageCode, string> = {
  en: "English", hi: "Hindi", bn: "Bengali", mr: "Marathi", te: "Telugu", ta: "Tamil", gu: "Gujarati", ur: "Urdu", kn: "Kannada", or: "Odia",
  ml: "Malayalam", pa: "Punjabi", as: "Assamese",
};

/** The locale used to write dates and numbers in each language. */
export const LANGUAGE_LOCALES: Record<LanguageCode, string> = {
  en: "en-GB", hi: "hi-IN", bn: "bn-IN", mr: "mr-IN", te: "te-IN", ta: "ta-IN", gu: "gu-IN", ur: "ur-IN", kn: "kn-IN", or: "or-IN",
  ml: "ml-IN", pa: "pa-IN", as: "as-IN",
};

/** Urdu is written right to left; every other language here is left to right. */
export const RIGHT_TO_LEFT_LANGUAGES: readonly LanguageCode[] = ["ur"];

export function directionOf(language: LanguageCode): "rtl" | "ltr" {
  return RIGHT_TO_LEFT_LANGUAGES.includes(language) ? "rtl" : "ltr";
}

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
