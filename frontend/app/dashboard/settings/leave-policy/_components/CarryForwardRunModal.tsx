"use client";

import Modal from "@/components/Modal";

interface Props {
  fromYear:     number;
  toYear:       number;
  pendingCount: number | null;
  running:      boolean;
  onConfirm:    () => void;
  onClose:      () => void;
}

export default function CarryForwardRunModal({ fromYear, toYear, pendingCount, running, onConfirm, onClose }: Props) {
  return (
    <Modal
      title={<><i className="ti ti-alert-triangle" style={{ marginRight: 8 }} />Run Carry Forward</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={running}>Cancel</button>
          <button className="btn btn-filled" style={{ background: "var(--error)" }} onClick={onConfirm} disabled={running}>
            {running ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />&nbsp;Running…</> : "Run Carry Forward"}
          </button>
        </>
      }
    >
      <p style={{ fontSize: 13, lineHeight: 1.6, color: "var(--on-bg)" }}>
        This will carry forward unused leave{pendingCount !== null ? ` for ${pendingCount} employee-leave combination${pendingCount !== 1 ? "s" : ""}` : ""} from{" "}
        <strong>{fromYear}</strong> to <strong>{toYear}</strong>. This cannot be undone. Continue?
      </p>
    </Modal>
  );
}
