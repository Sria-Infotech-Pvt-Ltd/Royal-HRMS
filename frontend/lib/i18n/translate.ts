// Looks up the wording for a piece of English text. The English text itself is the key, so a screen reads naturally in the code and
// anything not yet translated simply stays in English instead of showing a code like "nav.leave".
//
//   t("Sign in")                                  -> "साइन इन करें" in Hindi
//   t("Sign in to your {brand} account", { brand: "AIRA" })   -> {brand} is filled in after translating

import type { LanguageCode } from "./languages";
import { HINDI } from "./messages/hi";
import { TELUGU } from "./messages/te";
import { BENGALI } from "./messages/bn";
import { MARATHI } from "./messages/mr";
import { TAMIL } from "./messages/ta";
import { GUJARATI } from "./messages/gu";
import { URDU } from "./messages/ur";
import { KANNADA } from "./messages/kn";
import { ODIA } from "./messages/or";
import { MALAYALAM } from "./messages/ml";
import { PUNJABI } from "./messages/pa";
import { ASSAMESE } from "./messages/as";

export type Messages = Readonly<Record<string, string>>;
export type TranslateParams = Readonly<Record<string, string | number>>;

export const MESSAGES: Readonly<Record<Exclude<LanguageCode, "en">, Messages>> = {
  hi: HINDI, te: TELUGU, bn: BENGALI, mr: MARATHI, ta: TAMIL, gu: GUJARATI, ur: URDU, kn: KANNADA, or: ODIA, ml: MALAYALAM, pa: PUNJABI, as: ASSAMESE,
};

export function fillParams(text: string, params?: TranslateParams): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (placeholder, name: string) => (name in params ? String(params[name]) : placeholder));
}

export function translate(language: LanguageCode, text: string, params?: TranslateParams): string {
  const wording = language === "en" ? text : MESSAGES[language][text] ?? text;
  return fillParams(wording, params);
}
