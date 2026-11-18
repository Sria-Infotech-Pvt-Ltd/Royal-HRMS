"use client";

// A titled block of setting cards on the Settings landing page (Pinned or one category), as a grid or a list. The heading is plain text with
// a quiet count, so the cards stay the focus.

import type { SettingsLayout } from "@/hooks/useSettingsPrefs";
import SettingsCard from "./SettingsCard";
import type { SettingsItem } from "./settingsItems";

interface Props {
  label: string;
  blurb?: string;
  /** Hide the heading (a single chosen category is shown as one plain grid). */
  hideHeading?: boolean;
  items: SettingsItem[];
  layout: SettingsLayout;
  pinned: string[];
  onTogglePinned: (id: string) => void;
}

export default function SettingsSection({ label, blurb, hideHeading = false, items, layout, pinned, onTogglePinned }: Props) {
  if (items.length === 0) return null;
  return (
    <section aria-label={label} style={{ marginBottom: 24 }}>
      {!hideHeading && (
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, margin: "0 2px 10px" }}>
          <h2 style={{ margin: 0, fontSize: 13, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--on-variant)" }}>{label}</h2>
          <span style={{ fontSize: 12, color: "var(--outline)" }}>{items.length}</span>
          {blurb && <span style={{ fontSize: 12.5, color: "var(--on-variant)" }}>{blurb}</span>}
        </div>
      )}
      <div className="settings-cards-grid" style={layout === "list" ? { gridTemplateColumns: "minmax(0, 1fr)", gridAutoRows: 68, gap: 10 } : { gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gridAutoRows: 112, gap: 14 }}>
        {items.map(item => <SettingsCard key={item.id} item={item} layout={layout} isPinned={pinned.includes(item.id)} onTogglePinned={onTogglePinned} />)}
      </div>
    </section>
  );
}
