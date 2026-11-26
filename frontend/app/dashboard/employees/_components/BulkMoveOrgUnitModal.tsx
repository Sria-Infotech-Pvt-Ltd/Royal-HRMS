"use client";

// HR moves several employees to another org unit at once. An employee's org unit follows their position, so each person is
// matched to a vacant seat in the target unit (pre-filled, editable). The server ends each old placement, so the old seats
// show as vacant from the effective date, and it skips (with a reason) anyone it cannot move.

import { useState } from "react";
import Modal from "@/components/Modal";
import FieldError from "@/components/shared/FieldError";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";
import { useBulkMoveOrgUnit, type BulkMoveSkipped } from "@/hooks/useBulkMoveOrgUnit";
import { useT } from "@/hooks/useI18n";
import BulkMoveOrgUnitRows from "./BulkMoveOrgUnitRows";

interface BulkMoveOrgUnitModalProps { onClose: () => void; onDone: () => void }

export default function BulkMoveOrgUnitModal({ onClose, onDone }: BulkMoveOrgUnitModalProps) {
  const t = useT();
  const { showToast } = useToast();
  const { fieldErrors, handleError, clearAll } = useApiErrors();
  const move = useBulkMoveOrgUnit();
  const [isSaving, setIsSaving] = useState(false);
  const [skipped, setSkipped] = useState<BulkMoveSkipped[]>([]);
  const readyCount = move.chosenPeople.length - move.unmatchedCount;

  async function submit() {
    clearAll();
    setIsSaving(true);
    try {
      const result = await move.submit();
      showToast(t("{count} employee(s) moved.", { count: result.moved.length }), "success");
      setSkipped(result.skipped);
      onDone();
      if (result.skipped.length === 0) onClose();
    } catch (err: unknown) {
      handleError(err, t("Could not move the employees."));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      title={<div className="text-[18px] font-bold">{t("Move to another")} <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{t("org unit")}</span></div>}
      onClose={onClose}
      maxWidth={760}
      footer={
        <>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={isSaving}>{t("Close")}</button>
          <button className="btn btn-filled" type="button" onClick={submit} disabled={isSaving || readyCount === 0 || !move.toUnitId}>
            {isSaving ? t("Moving…") : t("Move {count} employee(s)", { count: readyCount })}
          </button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
          <div className="f">
            <label htmlFor="move-from">{t("Move from")}</label>
            <select id="move-from" className="finput" value={move.fromUnitId} onChange={event => move.chooseFromUnit(event.target.value)}>
              <option value="">{t("All org units")}</option>
              {move.activeUnits.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
            </select>
          </div>
          <div className="f">
            <label htmlFor="move-to">{t("Move to")}</label>
            <select id="move-to" className="finput" value={move.toUnitId} onChange={event => move.chooseToUnit(event.target.value)}>
              <option value="">{t("Select an org unit")}</option>
              {move.activeUnits.filter(unit => unit.id !== move.fromUnitId).map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
            </select>
          </div>
          <div className="f">
            <label htmlFor="move-date">{t("Effective date")}</label>
            <input id="move-date" type="date" className="finput" value={move.effectiveDate} onChange={event => move.setEffectiveDate(event.target.value)} />
            <FieldError message={fieldErrors.effective_date} />
          </div>
        </div>

        <div className="f">
          <label htmlFor="move-reason">{t("Reason")}</label>
          <input id="move-reason" className="finput" maxLength={500} value={move.reason} onChange={event => move.setReason(event.target.value)} placeholder={t("e.g. Team restructure")} />
        </div>

        {move.toUnitId && (
          <p className="hint">
            {t("{count} vacant position(s) in the target org unit.", { count: move.vacantSeats.length })}{" "}
            {move.unmatchedCount > 0 && t("{count} selected employee(s) have no vacant position left: add positions in Org Structure first.", { count: move.unmatchedCount })}
          </p>
        )}

        <FieldError message={fieldErrors.moves} />
        <BulkMoveOrgUnitRows move={move} />

        {skipped.length > 0 && (
          <div className="alert alert-warning" role="status">
            <i className="ti ti-alert-triangle" />
            <div>{t("{count} could not be changed:", { count: skipped.length })} {skipped.map(item => `${item.employee_id} (${item.reason})`).join("; ")}</div>
          </div>
        )}
      </div>
    </Modal>
  );
}
