"use client";

import { useT } from "@/hooks/useI18n";
import { STYLE_LABELS, THEME_STYLES, type ThemeStyle } from "@/lib/theme";

interface ThemeStyleChoicesProps {
  selected: ThemeStyle;
  onSelect: (style: ThemeStyle) => void;
}

// The look of the app (shapes, spacing, shadows), shown as small previews so a person can see what they are choosing.
export default function ThemeStyleChoices({ selected, onSelect }: ThemeStyleChoicesProps) {
  const t = useT();
  return (
    <div role="group" aria-label={t("Look")} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      {THEME_STYLES.map(style => {
        const isSelected = selected === style;
        return (
          <button key={style} type="button" aria-pressed={isSelected} onClick={() => onSelect(style)} style={{
            textAlign: "left", padding: 8, borderRadius: 12, cursor: "pointer", color: "var(--ink)",
            border: `1px solid ${isSelected ? "var(--brand)" : "var(--line)"}`, background: isSelected ? "var(--brand-tint)" : "var(--surface)",
          }}>
            <span aria-hidden="true" data-style-preview={style} style={{ display: "block", height: 34, marginBottom: 6, ...PREVIEWS[style] }} />
            <span style={{ display: "block", fontSize: 12.5, fontWeight: 700 }}>{t(STYLE_LABELS[style].label)}</span>
            <span style={{ display: "block", fontSize: 10.5, color: "var(--muted)", lineHeight: 1.3 }}>{t(STYLE_LABELS[style].hint)}</span>
          </button>
        );
      })}
    </div>
  );
}

// Each preview is a tiny card drawn the way that look draws cards.
const PREVIEWS: Record<ThemeStyle, React.CSSProperties> = {
  classic: { borderRadius: 8, background: "var(--surface-2)", border: "1px solid var(--line)" },
  soft: { borderRadius: 16, background: "var(--surface)", boxShadow: "0 5px 14px rgba(30,24,60,.18)" },
  compact: { borderRadius: 4, background: "repeating-linear-gradient(var(--surface-2) 0 5px, var(--line) 5px 6px)", border: "1px solid var(--line)" },
  glass: { borderRadius: 12, background: "linear-gradient(135deg, var(--brand), var(--brand-2))", boxShadow: "inset 0 0 0 9999px rgba(255,255,255,.35)" },
  amoled: { borderRadius: 8, background: "#000", border: "1px solid #2a2a33" },
  contrast: { borderRadius: 6, background: "var(--surface)", border: "3px solid var(--ink)" },
};
