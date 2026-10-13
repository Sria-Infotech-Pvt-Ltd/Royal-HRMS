"use client";

// Reference .ess-actions grid: nine tiles, a small glyph chip + title + hint,
// rendered as one continuous grid exactly as the reference shows it.

interface Action { glyph: string; title: string; sub: string; onClick: () => void }

export default function HomeQuickActions({ actions }: { actions: Action[] }) {
  return (
    <section className="ess-card">
      <h2>Quick actions</h2>
      <p>Complete common employee tasks without contacting HR.</p>
      <div className="ess-actions">
        {actions.map(a => (
          <button key={a.title} type="button" className="ess-action" onClick={a.onClick}>
            <span className="ea-ico">{a.glyph}</span>
            <strong>{a.title}</strong>
            <small>{a.sub}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
