// A plain translate function for screens that are not wrapped in a hook: `tr("Sign in")`. It reads the language the provider last set.
// This is safe because I18nProvider remounts the app when the language changes (see components/I18nProvider.tsx), so every `tr(...)`
// in the tree is evaluated again. Labels held in module-level constants are evaluated once, so translate them where they are rendered.

import { DEFAULT_LANGUAGE, type LanguageCode } from "./languages";
import { translate, type TranslateParams } from "./translate";

let activeLanguage: LanguageCode = DEFAULT_LANGUAGE;

export function setActiveLanguage(language: LanguageCode): void {
  activeLanguage = language;
}

export function getActiveLanguage(): LanguageCode {
  return activeLanguage;
}

export function tr(text: string, params?: TranslateParams): string {
  return translate(activeLanguage, text, params);
}
