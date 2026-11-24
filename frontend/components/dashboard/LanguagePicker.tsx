"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguageSync } from "@/hooks/useLanguageSync";
import { useT } from "@/hooks/useI18n";
import LanguageOptions from "@/components/LanguageOptions";

// The header button for choosing the language the screens are shown in.
export default function LanguagePicker() {
  const t = useT();
  const { language, choose } = useLanguageSync();
  const [isOpen, setIsOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onPointer = (event: MouseEvent) => { if (!container.current?.contains(event.target as Node)) setIsOpen(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setIsOpen(false); };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onPointer); document.removeEventListener("keydown", onKey); };
  }, [isOpen]);

  return (
    <div ref={container} style={{ position: "relative" }}>
      <button type="button" className="iconbtn" title={t("Language")} aria-label={t("Language")} aria-haspopup="dialog" aria-expanded={isOpen} onClick={() => setIsOpen(open => !open)}>
        <i className="ti ti-language" aria-hidden="true" style={{ fontSize: 16 }} />
      </button>
      {isOpen && (
        <div role="dialog" aria-label={t("Choose a language")} style={{
          position: "absolute", insetInlineEnd: 0, top: "calc(100% + 8px)", width: "min(380px, calc(100vw - 24px))", maxHeight: "min(78vh, 480px)",
          overflowY: "auto", padding: 12, zIndex: 60, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 14,
          boxShadow: "0 14px 40px rgba(20,16,40,.18)",
        }}>
          <LanguageOptions selected={language} onChoose={code => { choose(code); setIsOpen(false); }} />
        </div>
      )}
    </div>
  );
}
