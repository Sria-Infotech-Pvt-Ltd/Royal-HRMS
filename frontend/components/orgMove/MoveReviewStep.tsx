"use client";

// The check before saving a "Move employees" change: a one-line summary, then each person's position and unit now and
// after the move, and who is left out because no position was found for them.

import { useT } from "@/hooks/useI18n";
import type { BulkMove } from "@/hooks/useBulkMoveOrgUnit";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import { initialsOf } from "@/lib/accessListView";
import styles from "./orgMove.module.css";

interface MoveReviewStepProps { move: BulkMove }

export function formatMoveDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export default function MoveReviewStep({ move }: MoveReviewStepProps) {
  const t = useT();
  const target = move.unitName(move.toUnitId);
  const moving = move.chosenPeople.filter(person => move.seatFor[person.employee_id]);
  const leftOut = move.chosenPeople.filter(person => !move.seatFor[person.employee_id]);
  const date = formatMoveDate(move.effectiveDate);
  const columns = "minmax(0,1.2fr) minmax(0,1fr) 24px minmax(0,1fr)";

  return (
    <div style={{ padding: "18px 24px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <h3 style={{ fontSize: 20, fontWeight: 800 }}>{t("Review and confirm")}</h3>
        <p className="hint" style={{ fontSize: 12.5, marginTop: 4 }}>
          {t("{count} employee(s) move to {unit} on {date}. Nothing is saved until you confirm.", { count: moving.length, unit: target, date })}
        </p>
      </div>

      <div role="table" aria-label={t("Review and confirm")}>
        <div role="row" style={{ display: "grid", gridTemplateColumns: columns, gap: 12, padding: "0 0 8px", fontSize: 10.5, fontWeight: 800, letterSpacing: ".08em", color: "var(--faint)", borderBottom: "1px solid var(--line-soft)" }}>
          <span role="columnheader">{t("EMPLOYEE")}</span><span role="columnheader">{t("NOW")}</span><span aria-hidden="true" /><span role="columnheader">{t("AFTER THE MOVE")}</span>
        </div>
        {moving.map(person => {
          const seat = move.vacantSeats.find(option => option.id === move.seatFor[person.employee_id]);
          return (
            <div role="row" key={person.employee_id} style={{ display: "grid", gridTemplateColumns: columns, gap: 12, alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line-soft)", fontSize: 12.5 }}>
              <span role="cell" style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
                <Avatar text={initialsOf(person.full_name)} size={28} photoUrl={person.profile_photo_url} />
                <span className={styles.personText}><b>{person.full_name}</b><small>{person.employee_id}</small></span>
              </span>
              <span role="cell" className={styles.personText}><b style={{ fontWeight: 500, color: "var(--muted)" }}>{person.designation || t("No position")}</b><small>{move.unitName(person.org_unit_id) || t("No org unit")}</small></span>
              <i className="ti ti-arrow-right" style={{ color: "var(--faint)" }} aria-hidden="true" />
              <span role="cell" className={styles.personText}><b style={{ color: "var(--brand-ink)" }}>{seat?.title}</b><small>{target}</small></span>
            </div>
          );
        })}
      </div>

      {leftOut.length > 0 && (
        <p className="hint bad" style={{ fontSize: 12 }}>
          {t("{count} will not be moved", { count: leftOut.length })}: {t("No position was chosen for: {names}.", { names: leftOut.map(person => person.full_name).join(", ") })}
        </p>
      )}

      <p className="hint" style={{ fontSize: 12 }}>
        <i className="ti ti-info-circle" /> {t("Each person moves to their new position on {date}, their old position becomes vacant from that day, and every change is written to the audit log. To undo, move them back the same way.", { date })}
        {move.reason && <> {t("Reason: {reason}", { reason: move.reason })}</>}
      </p>
    </div>
  );
}
