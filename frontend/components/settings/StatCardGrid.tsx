"use client";

export interface StatCard {
  icon: string;
  tone: string;
  label: string;
  value: string;
  note: string;
}

/** A row of summary cards: an icon in a tinted square, a small caps label, a big number and a one-line note. */
export default function StatCardGrid({ cards }: { cards: StatCard[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map(card => (
        <div key={card.label} className="flex items-center gap-3 rounded-2xl border border-[var(--outline-v)] p-3.5" style={{ background: "var(--surface)" }}>
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg" style={{ background: `color-mix(in srgb, ${card.tone} 14%, transparent)`, color: card.tone }}>
            <i className={`ti ${card.icon}`} />
          </span>
          <div className="min-w-0">
            <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">{card.label}</div>
            <div className="text-xl font-bold leading-tight text-[var(--on-bg)]">{card.value}</div>
            <div className="truncate text-[11.5px] text-[var(--on-variant)]">{card.note}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
