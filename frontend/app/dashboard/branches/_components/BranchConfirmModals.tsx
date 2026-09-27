"use client";

import Modal from "@/components/Modal";
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
  return (
    <Modal
      title={
        <>
          <i className="ti ti-arrows-right-left" style={{ marginRight: "8px", color: "var(--primary)" }} />
          Move {state.employee.full_name}?
        </>
      }
      onClose={onClose}
      maxWidth="440px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={onConfirm}>Yes, Move Them</button>
        </>
      }
    >
      <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6, marginBottom: (state.reportsCount > 0 || state.hrForCount > 0) ? "14px" : 0 }}>
        <strong>{state.employee.full_name}</strong> currently belongs to{" "}
        <strong>{state.employee.branch || "no Company Code"}</strong>. This will move them to the new Company Code
        and change their role to Company Code Admin.
      </p>
      {(state.reportsCount > 0 || state.hrForCount > 0) && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <div>
            {state.reportsCount > 0 && (
              <div>They currently manage {state.reportsCount} {state.reportsCount === 1 ? "employee" : "employees"} — that reporting line won&apos;t be reassigned automatically.</div>
            )}
            {state.hrForCount > 0 && (
              <div>They&apos;re the assigned HR for {state.hrForCount} {state.hrForCount === 1 ? "employee" : "employees"} — that assignment won&apos;t be reassigned automatically.</div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export function HqConfirmModal({ onClose, onConfirm }: { onClose: () => void; onConfirm: () => void }) {
  return (
    <Modal
      title={
        <>
          <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--warn)" }} />
          Change Headquarter?
        </>
      }
      onClose={onClose}
      maxWidth="420px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={onConfirm}>Yes, Change HQ</button>
        </>
      }
    >
      <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
        Another branch is already marked as the headquarter. Setting this branch as HQ will remove the HQ status from the existing one. Do you want to continue?
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
  return (
    <Modal
      title={
        <>
          <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--error)" }} />
          Delete Company Code?
        </>
      }
      onClose={onClose}
      closeDisabled={deleting}
      maxWidth="420px"
      zIndex={1010}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={deleting}>Cancel</button>
          <button
            className="btn btn-filled"
            style={{ background: "var(--error-solid)" }}
            onClick={onConfirm}
            disabled={deleting}
          >
            {deleting
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Deleting…</>
              : "Yes, Delete"}
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
        Are you sure you want to delete <strong>{branchName}</strong>? This action cannot be undone.
      </p>
    </Modal>
  );
}
