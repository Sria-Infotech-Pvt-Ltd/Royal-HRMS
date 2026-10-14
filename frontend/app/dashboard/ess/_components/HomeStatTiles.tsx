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
  // 4 separate cards (same .card box — border, radius, shadow — every other
  // card on this page uses), not one joined bar with 1px divider lines: the
  // reference spec calls these "4 equal columns" of cards, same size/style
  // as Quick actions/Today/My requests, with the page's own 12px card gap.
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
      {tiles.map((t, i) => (
        <div key={i} className="card" style={{ padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--on-variant)", fontSize: 10, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
            <i className={`ti ${t.icon}`} /> {t.label}
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1, marginTop: 8 }}>{t.value}</div>
          <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>
            {t.sub} ·{" "}
            <button
              onClick={t.onClick}
              className="btn-link"
              style={{ border: "none", background: "transparent", padding: 0, cursor: "pointer", fontSize: 11, fontWeight: 500, color: "var(--primary)" }}
            >
              {t.linkText}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
