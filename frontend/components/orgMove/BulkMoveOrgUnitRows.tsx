"use client";

// The employee list inside "Move to another org unit": tick who moves, and see (or change) the vacant seat each one gets.

import { useT } from "@/hooks/useI18n";
import type { useBulkMoveOrgUnit } from "@/hooks/useBulkMoveOrgUnit";

interface BulkMoveOrgUnitRowsProps { move: ReturnType<typeof useBulkMoveOrgUnit> }

export default function BulkMoveOrgUnitRows({ move }: BulkMoveOrgUnitRowsProps) {
  const t = useT();
  if (move.isLoading) return <p className="hint">{t("Loading…")}</p>;
  if (move.people.length === 0) return <p className="hint">{t("No active employees in this org unit.")}</p>;

  // A seat already given to someone else in this move is not offered again.
  const seatsInUse = new Set(Object.entries(move.seatFor).filter(([code, seat]) => seat && move.selected.has(code)).map(([, seat]) => seat));

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
        <b style={{ fontSize: 13 }}>{t("Employees ({count})", { count: move.people.length })}</b>
        <button type="button" className="btn btn-ghost btn-sm" onClick={move.selectAll}>{t("Select all")}</button>
      </div>
      <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
        {move.people.map(person => {
          const code = person.employee_id;
          const isChosen = move.selected.has(code);
          const seat = move.seatFor[code] ?? "";
          return (
            <div key={code} className="flex items-center gap-2" style={{ padding: "8px 12px", fontSize: 13, flexWrap: "wrap" }}>
              <label className="flex items-center gap-2" style={{ cursor: "pointer", flex: "1 1 220px", minWidth: 0 }}>
                <input type="checkbox" checked={isChosen} onChange={() => move.toggle(code)} />
                <span>{person.full_name}</span>
                <span style={{ color: "var(--on-variant)" }}>{code} · {person.designation || t("No position")}</span>
              </label>
              {isChosen && move.toUnitId && (
                <select
                  className="finput" style={{ flex: "0 1 220px", minWidth: 160 }} aria-label={t("New position for {name}", { name: person.full_name })}
                  value={seat} onChange={event => move.chooseSeat(code, event.target.value)}
                >
                  <option value="">{t("No vacant position")}</option>
                  {move.vacantSeats.filter(option => option.id === seat || !seatsInUse.has(option.id)).map(option => (
                    <option key={option.id} value={option.id}>{option.title}</option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
