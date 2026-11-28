"use client";

// The strip across the top of the "Move employees" board: from which unit, to which unit (with a swap button), when, and why.
// Unit options show how many people / vacant positions each has, so the right target is obvious before picking it.

import { useT } from "@/hooks/useI18n";
import type { BulkMove } from "@/hooks/useBulkMoveOrgUnit";
import { MOVE_REASON_MAX_LENGTH } from "@/lib/orgMove";
import styles from "./orgMove.module.css";

const REASON_PRESETS = ["Team restructure", "Project change", "Department merger", "Business need"];

interface MoveControlsBarProps { move: BulkMove }

export default function MoveControlsBar({ move }: MoveControlsBarProps) {
  const t = useT();
  return (
    <div className={styles.controls}>
      <div className="f">
        <label htmlFor="move-from">{t("Current org unit")}</label>
        <select id="move-from" className="finput" value={move.fromUnitId} onChange={event => move.setFromUnitId(event.target.value)}>
          <option value="">{t("All org units")}</option>
          {move.unitSummaries.map(({ unit, filled }) => <option key={unit.id} value={unit.id}>{unit.name} · {t("{count} people", { count: filled })}</option>)}
        </select>
      </div>
      <button type="button" className={styles.swap} onClick={move.swapUnits} disabled={!move.fromUnitId || !move.toUnitId} title={t("Swap the two units")} aria-label={t("Swap the two units")}>
        <i className="ti ti-arrows-exchange" />
      </button>
      <div className="f">
        <label htmlFor="move-to">{t("New org unit")} <span className="req">*</span></label>
        <select id="move-to" className="finput" value={move.toUnitId} onChange={event => move.chooseToUnit(event.target.value)}>
          <option value="">{t("Choose an org unit")}</option>
          {move.unitSummaries.filter(({ unit }) => unit.id !== move.fromUnitId).map(({ unit, vacant }) => (
            <option key={unit.id} value={unit.id}>{unit.name} · {t("{count} vacant", { count: vacant })}</option>
          ))}
        </select>
      </div>
      <div className="f">
        <label htmlFor="move-date">{t("Effective date")}</label>
        <input id="move-date" type="date" className="finput" value={move.effectiveDate} onChange={event => move.setEffectiveDate(event.target.value)} aria-invalid={move.isPastDate} style={move.isPastDate ? { borderColor: "var(--crit)" } : undefined} />
      </div>
      <div className="f">
        <label htmlFor="move-reason">{t("Reason")}</label>
        <input id="move-reason" className="finput" list="move-reason-presets" maxLength={MOVE_REASON_MAX_LENGTH} value={move.reason} onChange={event => move.setReason(event.target.value)} placeholder={t("e.g. Team restructure")} />
        <datalist id="move-reason-presets">{REASON_PRESETS.map(preset => <option key={preset} value={t(preset)} />)}</datalist>
      </div>
    </div>
  );
}
