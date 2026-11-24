"use client";

// A map of the whole ID number space: every worker type's range drawn to scale along one line, with the used part filled in. It follows
// the numbers as they are typed, shows the gaps between ranges, and draws any overlapping ranges in red.

import { useT } from "@/hooks/useI18n";
import { BRAND, leadingDigit, tint } from "./employeeCodeView";

export interface MapRange { type: string; label: string; start: number; end: number; next: number; isOverlapping: boolean }

export default function RangeMap({ ranges }: { ranges: MapRange[] }) {
  const t = useT();
  if (ranges.length === 0) return null;
  const low = Math.min(...ranges.map(range => range.start));
  const high = Math.max(...ranges.map(range => range.end));
  const span = Math.max(high - low + 1, 1);
  const percent = (value: number) => (value / span) * 100;

  return (
    <section aria-label={t("ID range map")} className="card" style={{ padding: "16px 20px", marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 800, color: "var(--on-bg)" }}>
          <i className="ti ti-ruler-measure" aria-hidden="true" style={{ color: BRAND }} /> {t("Range map")}
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 11.5, color: "var(--on-variant)" }}>
          <span><span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: BRAND, marginRight: 5 }} />{t("Used")}</span>
          <span><span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: tint(BRAND, 0.18), marginRight: 5 }} />{t("Still free")}</span>
          <span><span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 3, background: "#DC2626", marginRight: 5 }} />{t("Overlap")}</span>
        </div>
      </div>

      <div style={{ position: "relative", height: 40, borderRadius: 10, background: "var(--bg-low)", border: "1px solid var(--outline-v)" }}>
        {ranges.map(range => {
          const used = Math.min(Math.max((range.next - range.start) / (range.end - range.start + 1), 0), 1) * 100;
          const colour = range.isOverlapping ? "#DC2626" : BRAND;
          return (
            <div
              key={range.type} role="img" aria-label={range.isOverlapping ? t("{label}: {start} to {end}, overlaps another range", { label: range.label, start: range.start, end: range.end }) : t("{label}: {start} to {end}", { label: range.label, start: range.start, end: range.end })}
              title={t("{label}\n{start} – {end}\nNext: {next}", { label: range.label, start: range.start, end: range.end, next: range.next })}
              style={{ position: "absolute", top: 4, bottom: 4, left: `${percent(range.start - low)}%`, width: `${Math.max(percent(range.end - range.start + 1), 0.8)}%`, borderRadius: 7, overflow: "hidden", background: tint(colour, 0.18), border: `1.5px solid ${colour}`, transition: "left .2s ease, width .2s ease" }}
            >
              <div style={{ height: "100%", width: `${used}%`, background: colour, transition: "width .2s ease" }} />
              <span style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontSize: 12, fontWeight: 800, color: used > 55 ? "#fff" : colour, mixBlendMode: "normal" }}>{leadingDigit(range.start)}</span>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontFamily: "Menlo, Consolas, monospace", fontSize: 11, color: "var(--on-variant)" }}>
        <span>{low}</span><span>{high}</span>
      </div>
    </section>
  );
}
