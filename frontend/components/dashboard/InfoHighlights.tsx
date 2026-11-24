"use client";

import { useT } from "@/hooks/useI18n";

// A row of key facts for an information page: a big value over a short caption. Presentational only.

export interface InfoHighlight { value: string; label: string }

export default function InfoHighlights({ items, label }: { items: InfoHighlight[]; label: string }) {
  const t = useT();
  return (
    <div role="list" aria-label={t(label)} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 12, marginBottom: 16 }}>
      {items.map(item => (
        <div key={item.label} role="listitem" className="card" style={{ padding: "14px 16px" }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--primary)", lineHeight: 1.15 }}>{t(item.value)}</div>
          <div style={{ marginTop: 4, fontSize: 12.5, lineHeight: 1.4, color: "var(--on-variant)" }}>{t(item.label)}</div>
        </div>
      ))}
    </div>
  );
}
