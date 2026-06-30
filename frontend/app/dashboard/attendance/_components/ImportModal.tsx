"use client";

interface Props {
  onClose: () => void;
}

export default function ImportModal({ onClose }: Props) {
  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">
            <i className="ti ti-upload" style={{ marginRight: 8, color: "var(--primary)" }} />
            Import Attendance
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          <div className="alert alert-info mb-16">
            <i className="ti ti-info-circle" />
            <span>
              <strong>Supported formats:</strong> CSV, XLS, XLSX — max 5 MB.
              Template must match the standard Royal HRMS punch format.
            </span>
          </div>

          <div className="upload-zone mb-16">
            <i className="ti ti-folder-open" />
            <p style={{ fontWeight: 500, marginBottom: 4 }}>Click to select file or drag &amp; drop</p>
            <small>CSV · XLS · XLSX — max 5 MB</small>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Period From</label>
              <input type="date" className="field-input" defaultValue="2025-06-01" />
            </div>
            <div className="field-group">
              <label className="field-label">Period To</label>
              <input type="date" className="field-input" defaultValue="2025-06-30" />
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled">
            <i className="ti ti-upload" /> Upload &amp; Process
          </button>
        </div>
      </div>
    </div>
  );
}
