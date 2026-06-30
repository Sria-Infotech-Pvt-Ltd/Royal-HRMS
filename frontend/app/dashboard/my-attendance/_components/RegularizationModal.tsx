"use client";

interface Props {
  onClose: () => void;
  date?: string;
}

export default function RegularizationModal({ onClose, date = "2025-06-24" }: Props) {
  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">
            <i className="ti ti-file-description" style={{ marginRight: 8, color: "var(--warn)" }} />
            Attendance Correction Request
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          <div className="alert alert-warn mb-16">
            <i className="ti ti-alert-triangle" />
            <span>
              Submit a correction for a missed or incorrect punch. Your manager will review and approve
              within the regularization cutoff window (7 days after month end).
            </span>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Date</label>
              <input type="date" className="field-input" defaultValue={date} />
            </div>
            <div className="field-group">
              <label className="field-label">Punch Type</label>
              <select className="field-input">
                <option>Clock In (IN)</option>
                <option>Clock Out (OUT)</option>
                <option>Both IN &amp; OUT</option>
              </select>
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Correct In Time</label>
              <input type="time" className="field-input" defaultValue="09:05" />
            </div>
            <div className="field-group">
              <label className="field-label">Correct Out Time</label>
              <input type="time" className="field-input" defaultValue="18:10" />
            </div>
          </div>

          <div className="field-group mb-16">
            <label className="field-label">Reason</label>
            <select className="field-input">
              <option>Device malfunction / biometric error</option>
              <option>Forgot to punch</option>
              <option>Work from field (client visit)</option>
              <option>System / server downtime</option>
              <option>Other</option>
            </select>
          </div>

          <div className="field-group">
            <label className="field-label">Additional Notes (optional)</label>
            <textarea className="field-input" style={{ minHeight: 72 }} placeholder="Describe the situation..." />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled">
            <i className="ti ti-send" /> Submit Request
          </button>
        </div>
      </div>
    </div>
  );
}
