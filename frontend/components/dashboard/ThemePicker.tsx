"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "@/hooks/useTheme";
import { useT } from "@/hooks/useI18n";
import ThemeStyleChoices from "@/components/dashboard/ThemeStyleChoices";
import CustomColourEditor from "@/components/dashboard/CustomColourEditor";
import { ACCENT_LABELS, MODE_LABELS, THEME_ACCENTS, THEME_MODES } from "@/lib/theme";

const SECTION_LABEL = { fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)", margin: "0 0 8px" } as const;

// The header button for choosing the colour theme: light / dark / match device, and an accent colour.
export default function ThemePicker() {
  const t = useT();
  const { theme, choose } = useTheme();
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
      <button type="button" className="iconbtn" title={t("Theme")} aria-label={t("Theme")} aria-haspopup="dialog" aria-expanded={isOpen} onClick={() => setIsOpen(open => !open)}>
        <i className="ti ti-palette" aria-hidden="true" style={{ fontSize: 16 }} />
      </button>
      {isOpen && (
        <div role="dialog" aria-label={t("Choose a theme")} style={{
          position: "absolute", right: 0, top: "calc(100% + 8px)", width: 300, maxHeight: "min(78vh, 640px)", overflowY: "auto", padding: 14, zIndex: 60, background: "var(--surface)",
          border: "1px solid var(--line)", borderRadius: 14, boxShadow: "0 14px 40px rgba(20,16,40,.18)",
        }}>
          <p style={SECTION_LABEL}>{t("Appearance")}</p>
          <div role="group" aria-label={t("Appearance")} style={{ display: "flex", gap: 6, marginBottom: 14 }}>
            {THEME_MODES.map(mode => {
              const isSelected = theme.mode === mode;
              return (
                <button key={mode} type="button" aria-pressed={isSelected} onClick={() => choose({ mode })} style={{
                  flex: 1, padding: "7px 4px", fontSize: 11.5, fontWeight: 600, borderRadius: 9, cursor: "pointer", lineHeight: 1.25,
                  border: `1px solid ${isSelected ? "var(--brand)" : "var(--line)"}`,
                  background: isSelected ? "var(--brand-tint)" : "var(--surface)", color: isSelected ? "var(--brand-ink)" : "var(--ink-2)",
                }}>{t(MODE_LABELS[mode])}</button>
              );
            })}
          </div>
          <p style={SECTION_LABEL}>{t("Look")}</p>
          <div style={{ marginBottom: 14 }}>
            {/* The pure-black look only exists in dark, so choosing it also switches the page to dark. */}
            <ThemeStyleChoices selected={theme.style} onSelect={style => choose(style === "amoled" ? { style, mode: "dark" } : { style })} />
          </div>
          <p style={SECTION_LABEL}>{t("Colour")}</p>
          <div role="group" aria-label={t("Colour")} style={{ display: "grid", gap: 6 }}>
            {THEME_ACCENTS.map(accent => {
              const isSelected = theme.accent === accent;
              return (
                <button key={accent} type="button" aria-pressed={isSelected} onClick={() => choose({ accent })} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 10, cursor: "pointer", textAlign: "left",
                  fontSize: 13, fontWeight: 600, border: `1px solid ${isSelected ? "var(--brand)" : "var(--line)"}`,
                  background: isSelected ? "var(--brand-tint)" : "var(--surface)", color: "var(--ink)",
                }}>
                  <span aria-hidden="true" style={{ width: 18, height: 18, borderRadius: "50%", background: ACCENT_LABELS[accent].swatch, flex: "none" }} />
                  <span style={{ flex: 1 }}>{t(ACCENT_LABELS[accent].label)}</span>
                  {isSelected && <i className="ti ti-check" aria-hidden="true" style={{ color: "var(--brand-ink)" }} />}
                </button>
              );
            })}
          </div>
          <p style={{ ...SECTION_LABEL, margin: "14px 0 8px" }}>{t("Your own colours")}</p>
          <CustomColourEditor custom={theme.custom} onChange={custom => choose({ custom })} />
        </div>
      )}
    </div>
  );
}
