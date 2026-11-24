"use client";

import { useEffect, useRef, useState } from "react";
import LanguageOptions from "@/components/LanguageOptions";
import { useI18n } from "@/hooks/useI18n";
import { LANGUAGE_NAMES } from "@/lib/i18n/languages";

// The language choice on the sign-in screen, where nobody is signed in yet: one small button showing the current language that opens the
// full list. It is kept in this browser, and once the person is signed in the choice saved on their profile (if any) takes over.
export default function LoginLanguageSwitch() {
  const { language, setLanguage, t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onPointer = (event: MouseEvent) => { if (!container.current?.contains(event.target as Node)) setIsOpen(false); };
    const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setIsOpen(false); };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onPointer); document.removeEventListener("keydown", onKey); };
  }, [isOpen]);

  return (
    <div ref={container} style={{ position: "relative", display: "flex", justifyContent: "center", marginTop: 18 }}>
      <button type="button" aria-haspopup="dialog" aria-expanded={isOpen} aria-label={t("Language")} onClick={() => setIsOpen(open => !open)} style={{
        display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer",
        border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink-2)",
      }}>
        <i className="ti ti-language" aria-hidden="true" style={{ fontSize: 16 }} />
        <span lang={language}>{LANGUAGE_NAMES[language]}</span>
        <i className={`ti ti-chevron-${isOpen ? "up" : "down"}`} aria-hidden="true" style={{ fontSize: 13, color: "var(--muted)" }} />
      </button>
      {isOpen && (
        <div role="dialog" aria-label={t("Choose a language")} style={{
          position: "absolute", bottom: "calc(100% + 10px)", left: "50%", transform: "translateX(-50%)", width: "min(400px, calc(100vw - 32px))",
          maxHeight: "min(60vh, 420px)", overflowY: "auto", padding: 12, zIndex: 60, background: "var(--surface)", border: "1px solid var(--line)",
          borderRadius: 16, boxShadow: "0 14px 40px rgba(20,16,40,.18)",
        }}>
          <LanguageOptions selected={language} onChoose={code => { setLanguage(code); setIsOpen(false); }} />
        </div>
      )}
    </div>
  );
}
