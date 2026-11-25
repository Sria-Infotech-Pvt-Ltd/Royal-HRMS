# Fonts of the app

Kept in the project on purpose: `next/font/local` serves them, so starting or building the app never downloads anything from Google.
All are open-source **variable** fonts (weights 100-900 in one file), licence **SIL Open Font License 1.1**
(Inter: the Inter Project Authors; Noto families: Google / The Noto Project Authors). They are free to use, bundle and redistribute.

| File | Font | Used for |
|------|------|----------|
| `inter-latin.woff2` | Inter (Latin subset) | the whole app: English text, digits, symbols |
| `noto-sans-devanagari-devanagari.woff2` | Noto Sans Devanagari | Hindi, Marathi |
| `noto-sans-bengali-bengali.woff2` | Noto Sans Bengali | Bengali, Assamese (also covers the letters ৰ and ৱ) |
| `noto-sans-telugu-telugu.woff2` | Noto Sans Telugu | Telugu |
| `noto-sans-tamil-tamil.woff2` | Noto Sans Tamil | Tamil |
| `noto-sans-gujarati-gujarati.woff2` | Noto Sans Gujarati | Gujarati |
| `noto-sans-kannada-kannada.woff2` | Noto Sans Kannada | Kannada |
| `noto-sans-oriya-oriya.woff2` | Noto Sans Oriya | Odia |
| `noto-sans-malayalam-malayalam.woff2` | Noto Sans Malayalam | Malayalam |
| `noto-sans-gurmukhi-gurmukhi.woff2` | Noto Sans Gurmukhi | Punjabi |
| `noto-naskh-arabic-arabic.woff2` | Noto Naskh Arabic | Urdu |

Source: the Fontsource packages (`@fontsource-variable/...`, files `<subset>-wght-normal.woff2`), downloaded once on 2026-11-25.
They are wired up in `lib/scriptFonts.ts`; `app/language-fonts.css` picks the font from `<html lang>`.

**Adding a language:** download that script's `<subset>-wght-normal.woff2` from the same package family, add a `localFont(...)` call
in `lib/scriptFonts.ts` and a `:root[lang="xx"]` line in `app/language-fonts.css`.
