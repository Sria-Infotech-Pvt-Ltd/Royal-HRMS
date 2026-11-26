"use client";

// "Move employees": a transfer board. Pick the From and To units at the top; choose people on the left; the target unit's
// vacant positions on the right fill automatically (same title first) and can be rearranged by drag and drop. A review
// screen shows every before -> after, and nothing is saved until it is confirmed. An employee's org unit follows their
// position, so the server ends each old placement (that position shows vacant from the effective date) and skips, with a
// reason, anyone it cannot move.

import { useState } from "react";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";
import { useBulkMoveOrgUnit, type BulkMoveResult } from "@/hooks/useBulkMoveOrgUnit";
import { useT } from "@/hooks/useI18n";
import MoveControlsBar from "./MoveControlsBar";
import MovePeoplePane from "./MovePeoplePane";
import MoveResultView from "./MoveResultView";
import MoveReviewStep, { formatMoveDate } from "./MoveReviewStep";
import MoveSeatsPane from "./MoveSeatsPane";
import styles from "./orgMove.module.css";

interface BulkMoveOrgUnitModalProps {
  onClose: () => void;
  onDone: () => void;
  /** Opened from an org unit in Organization Management: that unit is pre-selected as From. */
  initialFromUnitId?: string;
}

export default function BulkMoveOrgUnitModal({ onClose, onDone, initialFromUnitId }: BulkMoveOrgUnitModalProps) {
  const t = useT();
  const { showToast } = useToast();
  const { handleError } = useApiErrors();
  const move = useBulkMoveOrgUnit(initialFromUnitId);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<BulkMoveResult | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const waitingCount = move.chosenPeople.length - move.matchedCount;
  const canReview = move.matchedCount > 0 && Boolean(move.toUnitId) && !move.isPastDate;

  async function confirm() {
    setIsSaving(true);
    try {
      setNames(Object.fromEntries(move.chosenPeople.map(person => [person.employee_id, person.full_name])));
      const outcome = await move.submit();
      setResult(outcome);
      showToast(t("{count} employee(s) moved.", { count: outcome.moved.length }), outcome.skipped.length ? "info" : "success");
      onDone();
    } catch (err: unknown) {
      handleError(err, t("Could not move the employees."));
    } finally {
      setIsSaving(false);
    }
  }

  const title = (
    <div>
      <div className="text-[18px] font-bold">{t("Move")} <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{t("employees")}</span></div>
      <div className="text-[12px] mt-0.5" style={{ color: "var(--on-variant)", fontWeight: 400 }}>{t("Choose people on the left; drag them onto a vacant position on the right, or let them fill in by title.")}</div>
    </div>
  );

  const summary = (
    <div className={styles.summary}>
      <span><b>{move.matchedCount}</b> {t("moving")}</span>
      {move.toUnitId && <><i className={styles.dot} /><span>{t("to {unit}", { unit: move.unitName(move.toUnitId) })}</span></>}
      {waitingCount > 0 && <><i className={styles.dot} /><span style={{ color: "var(--warn)", fontWeight: 600 }}>{t("{count} without a position", { count: waitingCount })}</span></>}
      <i className={styles.dot} />
      <span style={move.isPastDate ? { color: "var(--crit)", fontWeight: 600 } : undefined}>
        {move.isPastDate ? t("Choose today or a later date.") : t("from {date}", { date: formatMoveDate(move.effectiveDate) })}
      </span>
    </div>
  );

  const footer = result ? (
    <div className="flex items-center gap-3 w-full justify-end"><button className="btn btn-filled" type="button" onClick={onClose}>{t("Done")}</button></div>
  ) : (
    <div className="flex items-center gap-3 w-full" style={{ flexWrap: "wrap" }}>
      <div style={{ flex: 1, minWidth: 220 }}>{summary}</div>
      <button className="btn btn-ghost" type="button" onClick={isReviewing ? () => setIsReviewing(false) : onClose} disabled={isSaving}>
        {isReviewing ? t("Back") : t("Cancel")}
      </button>
      {isReviewing ? (
        <button className="btn btn-filled" type="button" onClick={confirm} disabled={isSaving || !canReview}>
          {isSaving ? t("Moving…") : t("Move {count} employee(s)", { count: move.matchedCount })}
        </button>
      ) : (
        <button className="btn btn-filled" type="button" onClick={() => setIsReviewing(true)} disabled={!canReview}>
          {t("Review move")} <i className="ti ti-arrow-right" />
        </button>
      )}
    </div>
  );

  return (
    <Modal title={title} onClose={onClose} size="lg" maxWidth={1180} scrollBody closeDisabled={isSaving}
      bodyStyle={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column", minHeight: "min(640px, 72vh)" }} footer={footer}>
      {result ? (
        <div style={{ overflowY: "auto" }}><MoveResultView result={result} nameOf={code => names[code] ?? code} /></div>
      ) : isReviewing ? (
        <div style={{ overflowY: "auto" }}><MoveReviewStep move={move} /></div>
      ) : (
        <>
          <MoveControlsBar move={move} />
          <div className={styles.board}>
            <MovePeoplePane move={move} />
            <MoveSeatsPane move={move} />
          </div>
        </>
      )}
    </Modal>
  );
}
