"use client";
import { tr } from "@/lib/i18n/tr";

interface Action { icon: string; title: string; sub: string; onClick: () => void }

interface Props {
  primary:   Action[];
  secondary: Action[];
}

// Reference spec: one 3-column grid (column-gap 8px, row-gap 14px), every
// tile at least 90px tall, "light border, 8px radius, 10px/8px padding...
// hover = violet border + light violet bg... 26px rounded-square icon chip
// (bg var(--brand-tint), violet icon)". No divider between the two source lists
// (primary/secondary) — the reference treats all 9 as one sequential grid.
// Colors use the app's theme tokens (color-mix against --primary) rather
// than the spec's literal hex so this still works in dark mode too.
// The grid itself lives in ess-theme.css (.ess-quick-grid): it drops to 2
// columns when the card is narrow (phones, or beside Today on a tablet).
export default function HomeQuickActions({ primary, secondary }: Props) {
  const tiles = [...primary, ...secondary];
  return (
    <div className="card ess-quick">
      <div className="card-header" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
        <div className="card-title"><i className="ti ti-bolt" /> {tr("Quick actions")}</div>
        <p style={{ margin: 0, fontSize: 11, color: "var(--on-variant)" }}>{tr("Complete common employee tasks without contacting HR.")}</p>
      </div>
      <div className="ess-quick-grid">
        {tiles.map((a, i) => (
          <button
            key={i}
            type="button"
            onClick={a.onClick}
            className="ess-quick-tile"
          >
            <span style={{
              width: 26, height: 26, borderRadius: 6, flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "color-mix(in srgb, var(--primary) 14%, var(--surface))",
            }}>
              <i className={`ti ${a.icon}`} style={{ fontSize: 14, color: "var(--primary)" }} />
            </span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 12, color: "var(--on-bg)" }}>{a.title}</div>
              <div style={{ fontSize: 10, color: "var(--on-variant)", lineHeight: 1.35, marginTop: 3 }}>{a.sub}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
