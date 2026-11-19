"use client";

import { useI18n } from "@/hooks/useI18n";
import { LANGUAGES, LANGUAGE_NAMES } from "@/lib/i18n/languages";

// The language choice on the sign-in screen, where nobody is signed in yet: it is kept in this browser, and once the person is signed in
// the choice saved on their profile (if any) takes over.
export default function LoginLanguageSwitch() {
  const { language, setLanguage, t } = useI18n();
  return (
    <div role="group" aria-label={t("Language")} style={{ display: "flex", justifyContent: "center", gap: 6, marginTop: 18, flexWrap: "wrap" }}>
      {LANGUAGES.map(code => {
        const isSelected = language === code;
        return (
          <button
            key={code} type="button" lang={code} aria-pressed={isSelected} onClick={() => setLanguage(code)}
            style={{
              padding: "5px 12px", borderRadius: 999, fontSize: 12.5, fontWeight: 600, cursor: "pointer",
              border: `1px solid ${isSelected ? "var(--brand)" : "var(--line)"}`,
              background: isSelected ? "var(--brand-tint)" : "transparent", color: isSelected ? "var(--brand-ink)" : "var(--muted)",
            }}
          >
            {LANGUAGE_NAMES[code]}
          </button>
        );
      })}
    </div>
  );
}
