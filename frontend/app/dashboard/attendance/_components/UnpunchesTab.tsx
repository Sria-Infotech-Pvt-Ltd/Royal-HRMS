"use client";

interface UnpunchRecord {
  id: number;
  name: string;
  employeeId: string;
  initials: string;
  date: string;
  clockIn: string;
  expectedOut: string;
  branch: string;
}

const UNPUNCHES: UnpunchRecord[] = [
  { id: 1, name: "Vikram Singh",  employeeId: "E007", initials: "VS", date: "28 Jun 2025", clockIn: "09:18", expectedOut: "18:00", branch: "Mumbai Office"   },
  { id: 2, name: "Karthik Raj",   employeeId: "E005", initials: "KR", date: "27 Jun 2025", clockIn: "08:55", expectedOut: "18:00", branch: "Chennai HQ"     },
  { id: 3, name: "Lakshmi Rao",   employeeId: "E010", initials: "LR", date: "27 Jun 2025", clockIn: "09:00", expectedOut: "18:00", branch: "Chennai HQ"     },
  { id: 4, name: "Arun Krishnan", employeeId: "E009", initials: "AK", date: "26 Jun 2025", clockIn: "09:03", expectedOut: "18:00", branch: "Bengaluru Tech" },
];

export default function UnpunchesTab() {
  return (
    <>
      <div className="alert alert-warn mb-16">
        <i className="ti ti-alert-triangle" />
        <span>
          These employees have a Clock In but no matching Clock Out for that day.
          The system cannot compute their total hours until the missing punch is resolved.
        </span>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Date</th>
                <th>Clock In</th>
                <th>Missing</th>
                <th>Expected Out</th>
                <th>Branch</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {UNPUNCHES.map(r => (
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
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.clockIn}</td>
                  <td><span className="badge badge-error">OUT missing</span></td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.expectedOut}</td>
                  <td>{r.branch}</td>
                  <td>
                    <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11 }}>
                      <i className="ti ti-clock-plus" /> Add Punch
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
