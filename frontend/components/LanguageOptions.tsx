"use client";

import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useT } from "@/hooks/useI18n";
import { LANGUAGES, LANGUAGE_ENGLISH_NAMES, LANGUAGE_NAMES, type LanguageCode } from "@/lib/i18n/languages";

interface LanguageOptionsProps {
  selected: LanguageCode;
  onChoose: (language: LanguageCode) => void;
}

const COLUMNS = 3;

function matches(code: LanguageCode, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return LANGUAGE_NAMES[code].toLowerCase().includes(needle) || LANGUAGE_ENGLISH_NAMES[code].toLowerCase().includes(needle);
}

// The list of languages, shared by the sign-in screen and the header: each one in its own script with its English name underneath,
// a search box, and arrow keys to move around the grid.
export default function LanguageOptions({ selected, onChoose }: LanguageOptionsProps) {
  const t = useT();
  const [query, setQuery] = useState("");
  const grid = useRef<HTMLDivElement>(null);
  const visible = useMemo(() => LANGUAGES.filter(code => matches(code, query)), [query]);

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const buttons = [...(grid.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: COLUMNS, ArrowUp: -COLUMNS }[event.key];
    if (step === undefined || current < 0) return;
    event.preventDefault();
    buttons[Math.min(buttons.length - 1, Math.max(0, current + step))]?.focus();
  }

  return (
    <div>
      <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t("Search languages")}
        aria-label={t("Search languages")} style={{
          width: "100%", marginBottom: 8, padding: "8px 10px", fontSize: 13, borderRadius: 10, border: "1px solid var(--line)",
          background: "var(--surface-2)", color: "var(--ink)",
        }} />
      <div ref={grid} onKeyDown={move} style={{ display: "grid", gridTemplateColumns: `repeat(${COLUMNS}, minmax(0, 1fr))`, gap: 6 }}>
        {visible.map(code => {
          const isSelected = selected === code;
          return (
            <button key={code} type="button" lang={code} aria-pressed={isSelected} onClick={() => onChoose(code)} style={{
              display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 1, padding: "8px 10px", borderRadius: 10, cursor: "pointer",
              textAlign: "start", minWidth: 0, color: "var(--ink)", position: "relative",
              border: `1px solid ${isSelected ? "var(--brand)" : "var(--line)"}`, background: isSelected ? "var(--brand-tint)" : "var(--surface)",
            }}>
              <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.35 }}>{LANGUAGE_NAMES[code]}</span>
              <span lang="en" style={{ fontSize: 10.5, color: "var(--muted)" }}>{LANGUAGE_ENGLISH_NAMES[code]}</span>
              {isSelected && <i className="ti ti-check" aria-hidden="true" style={{ position: "absolute", top: 8, insetInlineEnd: 8, fontSize: 13, color: "var(--brand-ink)" }} />}
            </button>
          );
        })}
      </div>
      {visible.length === 0 && <p role="status" style={{ margin: "8px 2px 0", fontSize: 12.5, color: "var(--muted)" }}>{t("No language matches that.")}</p>}
    </div>
  );
}
