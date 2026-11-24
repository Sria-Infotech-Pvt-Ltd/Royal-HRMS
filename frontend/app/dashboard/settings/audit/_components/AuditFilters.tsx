"use client";

// The Audit Log filters: coloured module buttons, quick date ranges with exact From and To dates, and a search for the person who acted.

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import DateInput from "@/components/shared/DateInput";
import type { AuditFilters as Filters } from "@/hooks/useAuditLog";
import { MODULES, RANGES, matchingRange, rangeDates, tint } from "./auditView";

interface Props { filters: Filters; todayISO: string; onChange: (change: Partial<Filters>) => void; onClear: () => void; isChanged: boolean }

const BRAND = "var(--brand)";

function Chip({ selected, colour, onClick, children }: { selected: boolean; colour: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onClick}
      style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 13px", borderRadius: 999, fontSize: 12.5, fontWeight: 700, cursor: "pointer", transition: "all .15s ease", border: `1.5px solid ${selected ? colour : "var(--outline-v)"}`, background: selected ? tint(colour, 0.12) : "var(--surface)", color: selected ? colour : "var(--on-variant)" }}>
      {children}
    </button>
  );
}

export default function AuditFilters({ filters, todayISO, onChange, onClear, isChanged }: Props) {
  const t = useT();
  const [draft, setDraft] = useState(filters.search);
  const range = matchingRange(filters.dateFrom, filters.dateTo, todayISO);

  return (
    <section aria-label={t("Filters")} className="card" style={{ padding: "16px 20px", marginBottom: 18, display: "flex", flexDirection: "column", gap: 14 }}>
      <div role="group" aria-label={t("Module")} style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Chip selected={filters.module === ""} colour={BRAND} onClick={() => onChange({ module: "" })}><i className="ti ti-layout-grid" aria-hidden="true" /> {t("All modules")}</Chip>
        {MODULES.map(module => (
          <Chip key={module.value} selected={filters.module === module.value} colour={module.colour} onClick={() => onChange({ module: module.value })}>
            <i className={`ti ${module.icon}`} aria-hidden="true" /> {t(module.label)}
          </Chip>
        ))}
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div role="group" aria-label={t("Quick range")} style={{ display: "flex", gap: 6 }}>
          {RANGES.map(entry => (
            <Chip key={entry.key} selected={range === entry.key} colour={BRAND} onClick={() => { const dates = rangeDates(entry.key, todayISO); onChange({ dateFrom: dates.from, dateTo: dates.to }); }}>{t(entry.label)}</Chip>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div className="field-group" style={{ minWidth: 150, margin: 0 }}>
            <label className="field-label">{t("From")}</label>
            <DateInput className="field-input" value={filters.dateFrom} onChange={isoDate => onChange({ dateFrom: isoDate })} />
          </div>
          <div className="field-group" style={{ minWidth: 150, margin: 0 }}>
            <label className="field-label">{t("To")}</label>
            <DateInput className="field-input" value={filters.dateTo} onChange={isoDate => onChange({ dateTo: isoDate })} />
          </div>
        </div>
        <form onSubmit={event => { event.preventDefault(); onChange({ search: draft.trim() }); }} style={{ display: "flex", gap: 8, alignItems: "flex-end", flex: "1 1 260px" }}>
          <div className="field-group" style={{ flex: 1, margin: 0 }}>
            <label className="field-label" htmlFor="audit-actor">{t("Actor")}</label>
            <div style={{ position: "relative" }}>
              <i className="ti ti-search" aria-hidden="true" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)" }} />
              <input id="audit-actor" className="field-input" value={draft} onChange={event => setDraft(event.target.value)} placeholder={t("Name or email…")} style={{ paddingLeft: 34, width: "100%" }} />
            </div>
          </div>
          <button className="btn btn-filled" type="submit"><i className="ti ti-search" /> {t("Search")}</button>
          {isChanged && <button className="btn btn-ghost" type="button" onClick={() => { setDraft(""); onClear(); }}><i className="ti ti-x" /> {t("Clear")}</button>}
        </form>
      </div>
    </section>
  );
}
