"use client";

interface OtRecord {
  id: number;
  name: string;
  employeeId: string;
  initials: string;
  date: string;
  otHours: string;
  type: string;
  otAmount: string;
  approvedBy: string;
  status: "Approved" | "Pending";
}

const OT_RECORDS: OtRecord[] = [
  { id: 1, name: "Arjun Sharma",  employeeId: "E001", initials: "AS", date: "27 Jun 2025", otHours: "2h 00m", type: "Regular",  otAmount: "₹ 625",   approvedBy: "Sneha Iyer",   status: "Approved" },
  { id: 2, name: "Meera Pillai",  employeeId: "E006", initials: "MP", date: "28 Jun 2025", otHours: "1h 45m", type: "Regular",  otAmount: "₹ 547",   approvedBy: "Karthik Raj",  status: "Pending"  },
  { id: 3, name: "Nitin Joshi",   employeeId: "E011", initials: "NJ", date: "29 Jun 2025", otHours: "3h 20m", type: "Holiday",  otAmount: "₹ 2,083", approvedBy: "Sneha Iyer",   status: "Approved" },
];

export default function OtEntryTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Add OT form */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-plus-circle" /> Add OT Entry
          </div>
        </div>
        <div className="card-body">
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">Employee</label>
              <select className="field-input">
                <option>Arjun Sharma (E001)</option>
                <option>Meera Pillai (E006)</option>
                <option>Nitin Joshi (E011)</option>
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Date</label>
              <input type="date" className="field-input" defaultValue="2025-06-30" />
            </div>
            <div className="field-group">
              <label className="field-label">OT Type</label>
              <select className="field-input">
                <option>Regular (1.5×)</option>
                <option>Holiday (2.0×)</option>
                <option>Weekly Off (1.5×)</option>
              </select>
            </div>
          </div>
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">OT Start</label>
              <input type="time" className="field-input" defaultValue="18:00" />
            </div>
            <div className="field-group">
              <label className="field-label">OT End</label>
              <input type="time" className="field-input" defaultValue="20:00" />
            </div>
            <div className="field-group">
              <label className="field-label">Approved By</label>
              <select className="field-input">
                <option>Sneha Iyer (HR Manager)</option>
                <option>Karthik Raj (Finance Head)</option>
              </select>
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Reason / Work Done</label>
            <textarea className="field-input" style={{ minHeight: 72 }} placeholder="Describe the overtime work..." />
          </div>
          <div style={{ textAlign: "right" }}>
            <button className="btn btn-filled">
              <i className="ti ti-plus" /> Add OT Entry
            </button>
          </div>
        </div>
      </div>

      {/* OT records table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-list-details" /> OT Records
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Date</th>
                <th>OT Hours</th>
                <th>Type</th>
                <th>OT Amount</th>
                <th>Approved By</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {OT_RECORDS.map(r => (
                <tr key={r.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "rgba(30,78,140,0.1)", color: "var(--primary)", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        {r.initials}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{r.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employeeId}</div>
                      </div>
                    </div>
                  </td>
                  <td>{r.date}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.otHours}</td>
                  <td>{r.type}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, fontWeight: 600 }}>{r.otAmount}</td>
                  <td>{r.approvedBy}</td>
                  <td>
                    <span className={`badge ${r.status === "Approved" ? "badge-success" : "badge-warn"}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" style={{ padding: "3px 10px", fontSize: 11 }}>View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
