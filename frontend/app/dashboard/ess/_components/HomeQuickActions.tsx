"use client";

interface Action { icon: string; title: string; sub: string; onClick: () => void }

interface Props {
  primary:   Action[];
  secondary: Action[];
}

function TileGrid({ actions, minWidth }: { actions: Action[]; minWidth: number }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${minWidth}px, 1fr))`, gap: 14 }}>
      {actions.map((a, i) => (
        <button
          key={i}
          onClick={a.onClick}
          style={{ display: "flex", gap: 12, alignItems: "flex-start", textAlign: "left", padding: 14, border: "1px solid var(--outline-v)", borderRadius: 10, background: "transparent", cursor: "pointer" }}
        >
          <i className={`ti ${a.icon}`} style={{ fontSize: 18, color: "var(--primary)" }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{a.title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{a.sub}</div>
          </div>
        </button>
      ))}
    </div>
  );
}

export default function HomeQuickActions({ primary, secondary }: Props) {
  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-bolt" /> Quick actions</div>
      </div>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
        <TileGrid actions={primary} minWidth={220} />
        {secondary.length > 0 && (
          <>
            <div style={{ borderTop: "1px solid var(--outline-v)" }} />
            <TileGrid actions={secondary} minWidth={220} />
          </>
        )}
      </div>
    </div>
  );
}
