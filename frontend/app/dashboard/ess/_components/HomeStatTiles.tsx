"use client";

// The 4 top stat tiles — attendance, leave balance, next payday, my requests.
// All values come from data HomeTab.tsx already fetches; this component only
// renders them plus the "View details" / "View all" links.

interface Tile {
  icon:    string;
  label:   string;
  value:   string;
  sub:     string;
  linkText: string;
  onClick: () => void;
}

interface Props { tiles: Tile[] }

export default function HomeStatTiles({ tiles }: Props) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 1, background: "var(--outline-v)", borderRadius: "var(--radius-lg)", overflow: "hidden", marginBottom: 20 }}>
      {tiles.map((t, i) => (
        <div key={i} style={{ background: "var(--surface)", padding: "18px 22px", display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--on-variant)", fontSize: 11, fontWeight: 700, letterSpacing: "0.04em" }}>
            <i className={`ti ${t.icon}`} /> {t.label}
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--on-bg)" }}>{t.value}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{t.sub}</div>
          <button
            onClick={t.onClick}
            className="btn-link"
            style={{ marginTop: 4, alignSelf: "flex-start", border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 12, fontWeight: 600, color: "var(--primary)" }}
          >
            {t.linkText} <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
          </button>
        </div>
      ))}
    </div>
  );
}
