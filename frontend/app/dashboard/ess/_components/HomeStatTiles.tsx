"use client";

// The 4 top metric cards (reference: .ess-metrics > button.ess-metric) —
// attendance, leave balance, next payday, my requests. Every value comes from
// data HomeTab already fetches; each card is a button that opens its tab.

interface Tile {
  label:    string;
  value:    string;
  sub:      string;
  linkText: string;
  onClick:  () => void;
}

export default function HomeStatTiles({ tiles }: { tiles: Tile[] }) {
  return (
    <section className="ess-metrics">
      {tiles.map(t => (
        <button key={t.label} type="button" className="ess-metric" data-ess-page="" onClick={t.onClick}>
          <i>{t.label}</i>
          <b>{t.value}</b>
          <span>{t.sub} · {t.linkText}</span>
        </button>
      ))}
    </section>
  );
}
