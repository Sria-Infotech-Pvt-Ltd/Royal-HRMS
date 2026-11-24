"use client";

import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import type { ApiEmployeeOption } from "./_data";

export interface TransferConfirmState {
  employee: ApiEmployeeOption;
  reportsCount: number;
  hrForCount: number;
}

export function TransferConfirmModal({
  state, onClose, onConfirm,
}: {
  state: TransferConfirmState;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const t = useT();
  return (
    <Modal
      title={
        <>
          <i className="ti ti-arrows-right-left" style={{ marginRight: "8px", color: "var(--primary)" }} />
          {t("Move {name}?", { name: state.employee.full_name })}
        </>
      }
      onClose={onClose}
      maxWidth="440px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Cancel")}</button>
          <button className="btn btn-filled" onClick={onConfirm}>{t("Yes, Move Them")}</button>
        </>
      }
    >
      <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6, marginBottom: (state.reportsCount > 0 || state.hrForCount > 0) ? "14px" : 0 }}>
        <strong>{state.employee.full_name}</strong> {t("currently belongs to")}{" "}
        <strong>{state.employee.branch || t("no Company Code")}</strong>{t(". This will move them to this Company Code as its Company Code Admin.")}
      </p>
      {(state.reportsCount > 0 || state.hrForCount > 0) && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <div>
            {state.reportsCount > 0 && (
              <div>{state.reportsCount === 1
                ? t("They currently manage {count} employee — that reporting line won't be reassigned automatically.", { count: state.reportsCount })
                : t("They currently manage {count} employees — that reporting line won't be reassigned automatically.", { count: state.reportsCount })}</div>
            )}
            {state.hrForCount > 0 && (
              <div>{state.hrForCount === 1
                ? t("They're the assigned HR for {count} employee — that assignment won't be reassigned automatically.", { count: state.hrForCount })
                : t("They're the assigned HR for {count} employees — that assignment won't be reassigned automatically.", { count: state.hrForCount })}</div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export function HqConfirmModal({ onClose, onConfirm }: { onClose: () => void; onConfirm: () => void }) {
  const t = useT();
  return (
    <Modal
      title={
        <>
          <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--warn)" }} />
          {t("Change Headquarter?")}
        </>
      }
      onClose={onClose}
      maxWidth="420px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Cancel")}</button>
          <button className="btn btn-filled" onClick={onConfirm}>{t("Yes, Change HQ")}</button>
        </>
      }
    >
      <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
        {t("Another branch is already marked as the headquarter. Setting this branch as HQ will remove the HQ status from the existing one. Do you want to continue?")}
      </p>
    </Modal>
  );
}

export function DeleteConfirmModal({
  branchName, deleting, error, onClose, onConfirm,
}: {
  branchName: string;
  deleting: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const t = useT();
  return (
    <Modal
      title={
        <>
          <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--error)" }} />
          {t("Delete Company Code?")}
        </>
      }
      onClose={onClose}
      closeDisabled={deleting}
      maxWidth="420px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={deleting}>{t("Cancel")}</button>
          <button
            className="btn btn-filled"
            style={{ background: "var(--error-solid)" }}
            onClick={onConfirm}
            disabled={deleting}
          >
            {deleting
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />{t("Deleting…")}</>
              : t("Yes, Delete")}
          </button>
        </>
      }
    >
      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}
      <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
        {t("Are you sure you want to delete")} <strong>{branchName}</strong>{t("? This action cannot be undone.")}
      </p>
    </Modal>
  );
}
