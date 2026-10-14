"use client";

interface Action { icon: string; title: string; sub: string; onClick: () => void }

interface Props {
  primary:   Action[];
  secondary: Action[];
}

// Reference spec: one 3-column grid (column-gap 8px, row-gap 14px), every
// tile exactly 90px tall, "light border, 8px radius, 10px/8px padding...
// hover = violet border + light violet bg... 26px rounded-square icon chip
// (bg #F3EEFE, violet icon)". No divider between the two source lists
// (primary/secondary) — the reference treats all 9 as one sequential grid.
// Colors use the app's theme tokens (color-mix against --primary) rather
// than the spec's literal hex so this still works in dark mode too.
export default function HomeQuickActions({ primary, secondary }: Props) {
  const tiles = [...primary, ...secondary];
  return (
    <div className="card">
      <div className="card-header" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
        <div className="card-title"><i className="ti ti-bolt" /> Quick actions</div>
        <p style={{ margin: 0, fontSize: 11, color: "var(--on-variant)" }}>Complete common employee tasks without contacting HR.</p>
      </div>
      <div style={{ padding: "16px", display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", columnGap: 8, rowGap: 14 }}>
        {tiles.map((a, i) => (
          <button
            key={i}
            onClick={a.onClick}
            className="ess-quick-tile"
            style={{
              display: "flex", flexDirection: "column", gap: 10, height: 90,
              textAlign: "left", padding: "10px 8px", border: "1px solid var(--outline-v)",
              borderRadius: 8, background: "transparent", cursor: "pointer",
            }}
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
