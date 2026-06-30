"use client";

type IssueType = "no-match" | "duplicate" | "future";

interface InvalidPunch {
  id: number;
  deviceId: string;
  rawTime: string;
  biometricId: string;
  issue: string;
  issueType: IssueType;
  suggestedMatch: string;
  branch: string;
}

const ISSUE_BADGE: Record<IssueType, string> = {
  "no-match":  "badge badge-error",
  "duplicate": "badge badge-warn",
  "future":    "badge badge-error",
};

const PUNCHES: InvalidPunch[] = [
  { id: 1, deviceId: "DEV-CH-03", rawTime: "2025-06-29 09:04:12", biometricId: "BIO-00412", issue: "No employee match", issueType: "no-match",  suggestedMatch: "Rohit Verma (E003)?", branch: "Mumbai Office"   },
  { id: 2, deviceId: "DEV-BL-01", rawTime: "2025-06-29 18:55:33", biometricId: "BIO-00887", issue: "Duplicate punch",   issueType: "duplicate", suggestedMatch: "Meera Pillai (E006)", branch: "Bengaluru Tech" },
  { id: 3, deviceId: "DEV-CH-02", rawTime: "2025-06-28 14:22:09", biometricId: "BIO-00214", issue: "Future timestamp",  issueType: "future",    suggestedMatch: "Divya Menon (E008)",  branch: "Chennai HQ"     },
];

export default function InvalidPunchesTab() {
  return (
    <>
      <div className="alert alert-info mb-16">
        <i className="ti ti-alert-circle" />
        <span>
          These punches could not be matched to an employee or contain data errors.
          Review and fix each record before it affects payroll.
        </span>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Device ID</th>
                <th>Raw Punch Time</th>
                <th>Card / Bio ID</th>
                <th>Issue</th>
                <th>Suggested Match</th>
                <th>Branch</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {PUNCHES.map(p => (
                <tr key={p.id}>
                  <td>
                    <span style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: "var(--on-bg)", fontWeight: 600 }}>
                      {p.deviceId}
                    </span>
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{p.rawTime}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{p.biometricId}</td>
                  <td><span className={ISSUE_BADGE[p.issueType]}>{p.issue}</span></td>
                  <td style={{ color: "var(--on-variant)", fontSize: 12 }}>{p.suggestedMatch}</td>
                  <td>{p.branch}</td>
                  <td>
                    <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11 }}>
                      <i className="ti ti-tool" /> Fix
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
