// The fonts of the app, kept in the project (lib/fonts/*.woff2) and served by next/font/local: nothing is downloaded from Google when the
// app is started or built, so a blocked or slow connection can no longer break the app. They are open-source variable fonts
// (SIL Open Font License 1.1: Inter, and the Noto families by Google); see lib/fonts/README.md for where they came from.
// Each script font only has its own script (Latin letters and digits inside the text fall back to Inter, see app/language-fonts.css), and
// preload is off, so a page only downloads the font of the language it is shown in. next/font needs every option written out literally in
// each call (no spread, no shared constant), so they repeat on purpose.
import localFont from "next/font/local";

/** The main font of the whole app. Its className goes on <body>. */
export const interFont = localFont({
  src: "./fonts/inter-latin.woff2", weight: "100 900", display: "swap",
});

const devanagari = localFont({ src: "./fonts/noto-sans-devanagari-devanagari.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-devanagari" });
const bengali = localFont({ src: "./fonts/noto-sans-bengali-bengali.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-bengali" });
const telugu = localFont({ src: "./fonts/noto-sans-telugu-telugu.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-telugu" });
const tamil = localFont({ src: "./fonts/noto-sans-tamil-tamil.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-tamil" });
const gujarati = localFont({ src: "./fonts/noto-sans-gujarati-gujarati.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-gujarati" });
const kannada = localFont({ src: "./fonts/noto-sans-kannada-kannada.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-kannada" });
const odia = localFont({ src: "./fonts/noto-sans-oriya-oriya.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-odia" });
const malayalam = localFont({ src: "./fonts/noto-sans-malayalam-malayalam.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-malayalam" });
const gurmukhi = localFont({ src: "./fonts/noto-sans-gurmukhi-gurmukhi.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-gurmukhi" });
const arabic = localFont({ src: "./fonts/noto-naskh-arabic-arabic.woff2", weight: "100 900", display: "swap", preload: false, variable: "--font-arabic" });

/** Put these class names on <html>: they define the --font-* variables that language-fonts.css uses. */
export const SCRIPT_FONT_CLASSES = [devanagari, bengali, telugu, tamil, gujarati, kannada, odia, malayalam, gurmukhi, arabic]
  .map(font => font.variable).join(" ");
