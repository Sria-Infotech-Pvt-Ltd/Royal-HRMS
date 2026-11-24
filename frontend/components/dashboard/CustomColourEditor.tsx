"use client";

import { useT } from "@/hooks/useI18n";
import { CUSTOM_COLOUR_KEYS, CUSTOM_COLOUR_LABELS, wasAdjusted, type CustomColourKey, type CustomColours } from "@/lib/themeColors";

interface CustomColourEditorProps {
  custom: CustomColours;
  onChange: (custom: CustomColours) => void;
}

function without(custom: CustomColours, key: CustomColourKey): CustomColours {
  const rest: CustomColours = { ...custom };
  delete rest[key];
  return rest;
}

// What each colour box shows when the person has not picked one: the colour the theme already uses.
const THEME_VARIABLE: Record<CustomColourKey, string> = {
  brand: "--brand", background: "--ground", card: "--surface", text: "--ink", header: "--surface",
};

function shownColour(key: CustomColourKey, custom: CustomColours): string {
  const picked = custom[key];
  if (picked) return picked;
  const computed = getComputedStyle(document.documentElement).getPropertyValue(THEME_VARIABLE[key]).trim();
  return /^#[0-9a-f]{6}$/i.test(computed) ? computed : "#7c3aed";
}

// Pickers for the person's own colours. Text colours are kept readable automatically (see lib/themeColors.ts).
export default function CustomColourEditor({ custom, onChange }: CustomColourEditorProps) {
  const t = useT();
  const hasAny = Object.keys(custom).length > 0;
  return (
    <div>
      <div style={{ display: "grid", gap: 6 }}>
        {CUSTOM_COLOUR_KEYS.map(key => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5, fontWeight: 600, color: "var(--ink)" }}>
            <input type="color" aria-label={t(CUSTOM_COLOUR_LABELS[key])} value={shownColour(key, custom)}
              onChange={event => onChange({ ...custom, [key]: event.target.value.toLowerCase() })}
              style={{ width: 30, height: 26, padding: 0, border: "1px solid var(--line)", borderRadius: 6, background: "none", cursor: "pointer" }} />
            <span style={{ flex: 1 }}>{t(CUSTOM_COLOUR_LABELS[key])}</span>
            {custom[key] && (
              <button type="button" aria-label={`${t("Reset")}: ${t(CUSTOM_COLOUR_LABELS[key])}`} onClick={() => onChange(without(custom, key))} style={{ border: 0, background: "none", color: "var(--muted)", cursor: "pointer", fontSize: 12 }}>
                <i className="ti ti-x" aria-hidden="true" />
              </button>
            )}
          </label>
        ))}
      </div>
      {wasAdjusted(custom) && (
        <p role="status" style={{ margin: "8px 0 0", fontSize: 11, color: "var(--muted)", lineHeight: 1.4 }}>
          {t("Some colours were adjusted a little so the text stays easy to read.")}
        </p>
      )}
      {hasAny && (
        <button type="button" onClick={() => onChange({})} style={{
          marginTop: 10, width: "100%", padding: "7px 10px", borderRadius: 9, border: "1px solid var(--line)", background: "var(--surface)",
          color: "var(--ink-2)", fontSize: 12, fontWeight: 600, cursor: "pointer",
        }}>{t("Reset to the theme colours")}</button>
      )}
    </div>
  );
}
