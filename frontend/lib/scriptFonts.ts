// A font for each script the app can be shown in. Self-hosted by next/font (not a Google Fonts link). preload is off, so a page only
// downloads the font of the language it is actually shown in; app/language-fonts.css picks it from <html lang>.
// next/font needs every option written out literally in each call (no spread, no shared constant), so they repeat on purpose. Each asks for the
// variable-weight file (one request): listing several weights makes Turbopack dev fail with "queries have exactly one entry".
import {
  Noto_Sans_Bengali, Noto_Sans_Devanagari, Noto_Sans_Gujarati, Noto_Sans_Gurmukhi, Noto_Sans_Kannada, Noto_Sans_Malayalam,
  Noto_Naskh_Arabic, Noto_Sans_Oriya, Noto_Sans_Tamil, Noto_Sans_Telugu,
} from "next/font/google";

const devanagari = Noto_Sans_Devanagari({ display: "swap", preload: false, subsets: ["devanagari"], variable: "--font-devanagari" });
const bengali = Noto_Sans_Bengali({ display: "swap", preload: false, subsets: ["bengali"], variable: "--font-bengali" });
const telugu = Noto_Sans_Telugu({ display: "swap", preload: false, subsets: ["telugu"], variable: "--font-telugu" });
const tamil = Noto_Sans_Tamil({ display: "swap", preload: false, subsets: ["tamil"], variable: "--font-tamil" });
const gujarati = Noto_Sans_Gujarati({ display: "swap", preload: false, subsets: ["gujarati"], variable: "--font-gujarati" });
const kannada = Noto_Sans_Kannada({ display: "swap", preload: false, subsets: ["kannada"], variable: "--font-kannada" });
const odia = Noto_Sans_Oriya({ display: "swap", preload: false, subsets: ["oriya"], variable: "--font-odia" });
const malayalam = Noto_Sans_Malayalam({ display: "swap", preload: false, subsets: ["malayalam"], variable: "--font-malayalam" });
const gurmukhi = Noto_Sans_Gurmukhi({ display: "swap", preload: false, subsets: ["gurmukhi"], variable: "--font-gurmukhi" });
const arabic = Noto_Naskh_Arabic({ display: "swap", preload: false, subsets: ["arabic"], variable: "--font-arabic" });

/** Put these class names on <html>: they define the --font-* variables that language-fonts.css uses. */
export const SCRIPT_FONT_CLASSES = [devanagari, bengali, telugu, tamil, gujarati, kannada, odia, malayalam, gurmukhi, arabic]
  .map(font => font.variable).join(" ");
