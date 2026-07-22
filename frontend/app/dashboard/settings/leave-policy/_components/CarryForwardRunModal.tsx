"use client";

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
    <div className="modal-overlay open">
      <div className="modal" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-alert-triangle" style={{ marginRight: 8 }} />Run Carry Forward</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 13, lineHeight: 1.6, color: "var(--on-bg)" }}>
            This will carry forward unused leave{pendingCount !== null ? ` for ${pendingCount} employee-leave combination${pendingCount !== 1 ? "s" : ""}` : ""} from{" "}
            <strong>{fromYear}</strong> to <strong>{toYear}</strong>. This cannot be undone. Continue?
          </p>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={running}>Cancel</button>
          <button className="btn btn-filled" style={{ background: "var(--error)" }} onClick={onConfirm} disabled={running}>
            {running ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />&nbsp;Running…</> : "Run Carry Forward"}
          </button>
        </div>
      </div>
    </div>
  );
}
