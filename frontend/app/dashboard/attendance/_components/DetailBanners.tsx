"use client";

// The coloured plain-words messages above the times ("No punch recorded", "Arrived late" ...), and the day's note if there is one.

import { useT } from "@/hooks/useI18n";
import { tint } from "./attendancePalette";
import type { Banner } from "./detailView";

interface Props {
  banners: Banner[];
  note: string;
}

export default function DetailBanners({ banners, note }: Props) {
  const t = useT();
  if (banners.length === 0 && !note) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
      {banners.map(banner => (
        <div key={banner.key} role="status" style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "11px 14px", borderRadius: 12, background: tint(banner.colour, 0.1), border: `1px solid ${tint(banner.colour, 0.35)}`, borderLeft: `4px solid ${banner.colour}` }}>
          <i className={`ti ${banner.icon}`} aria-hidden="true" style={{ fontSize: 20, color: banner.colour, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{banner.title}</div>
            <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 1 }}>{banner.hint}</div>
          </div>
        </div>
      ))}
      {note && (
        <div style={{ display: "flex", gap: 10, padding: "10px 14px", borderRadius: 12, background: "var(--bg-low)", border: "1px solid var(--outline-v)", fontSize: 13 }}>
          <i className="ti ti-note" aria-hidden="true" style={{ color: "var(--on-variant)", fontSize: 17 }} />
          <span><strong style={{ fontWeight: 600 }}>{t("Note:")} </strong>{note}</span>
        </div>
      )}
    </div>
  );
}
