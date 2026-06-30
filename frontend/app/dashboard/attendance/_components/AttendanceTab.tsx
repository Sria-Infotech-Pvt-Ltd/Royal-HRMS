"use client";

import { useState } from "react";
import ImportModal from "./ImportModal";

type AttendanceStatus = "Present" | "Late" | "Absent" | "On Leave" | "Half Day" | "Weekly Off" | "Holiday";

interface AttendanceRecord {
  id: string;
  name: string;
  initials: string;
  department: string;
  branch: string;
  clockIn: string;
  clockOut: string;
  totalHours: string;
  ot: string;
  status: AttendanceStatus;
}

const BADGE_MAP: Record<AttendanceStatus, string> = {
  Present:     "badge badge-success",
  Late:        "badge badge-warn",
  Absent:      "badge badge-error",
  "On Leave":  "badge badge-info",
  "Half Day":  "badge badge-primary",
  "Weekly Off":"badge badge-neutral",
  Holiday:     "badge badge-neutral",
};

const ALL_RECORDS: AttendanceRecord[] = [
  { id: "E001", name: "Arjun Sharma",   initials: "AS", department: "Engineering",  branch: "Bengaluru Tech", clockIn: "09:05", clockOut: "18:15", totalHours: "9h 10m", ot: "10m",  status: "Present"  },
  { id: "E002", name: "Priya Nair",     initials: "PN", department: "Design",       branch: "Chennai HQ",     clockIn: "09:42", clockOut: "18:30", totalHours: "8h 48m", ot: "—",    status: "Late"     },
  { id: "E003", name: "Rohit Verma",    initials: "RV", department: "Sales",        branch: "Mumbai Office",  clockIn: "—",     clockOut: "—",     totalHours: "—",      ot: "—",    status: "Absent"   },
  { id: "E004", name: "Sneha Iyer",     initials: "SI", department: "HR",           branch: "Chennai HQ",     clockIn: "—",     clockOut: "—",     totalHours: "—",      ot: "—",    status: "On Leave" },
  { id: "E005", name: "Karthik Raj",    initials: "KR", department: "Finance",      branch: "Chennai HQ",     clockIn: "08:55", clockOut: "13:05", totalHours: "4h 10m", ot: "—",    status: "Half Day" },
  { id: "E006", name: "Meera Pillai",   initials: "MP", department: "Engineering",  branch: "Bengaluru Tech", clockIn: "09:02", clockOut: "18:45", totalHours: "9h 43m", ot: "43m",  status: "Present"  },
  { id: "E007", name: "Vikram Singh",   initials: "VS", department: "Operations",   branch: "Mumbai Office",  clockIn: "09:18", clockOut: "18:10", totalHours: "8h 52m", ot: "—",    status: "Late"     },
  { id: "E008", name: "Divya Menon",    initials: "DM", department: "Marketing",    branch: "Chennai HQ",     clockIn: "08:58", clockOut: "18:05", totalHours: "9h 07m", ot: "7m",   status: "Present"  },
  { id: "E009", name: "Arun Krishnan",  initials: "AK", department: "Engineering",  branch: "Bengaluru Tech", clockIn: "—",     clockOut: "—",     totalHours: "—",      ot: "—",    status: "Absent"   },
  { id: "E010", name: "Lakshmi Rao",    initials: "LR", department: "Admin",        branch: "Chennai HQ",     clockIn: "09:00", clockOut: "18:00", totalHours: "9h 00m", ot: "—",    status: "Present"  },
  { id: "E011", name: "Nitin Joshi",    initials: "NJ", department: "Sales",        branch: "Mumbai Office",  clockIn: "09:10", clockOut: "18:30", totalHours: "9h 20m", ot: "20m",  status: "Present"  },
  { id: "E012", name: "Ananya Bose",    initials: "AB", department: "Engineering",  branch: "Bengaluru Tech", clockIn: "—",     clockOut: "—",     totalHours: "—",      ot: "—",    status: "On Leave" },
];

const BRANCHES = ["All Branches", "Chennai HQ", "Mumbai Office", "Bengaluru Tech"];
const DEPARTMENTS = ["All Departments", "Engineering", "Design", "Sales", "HR", "Finance", "Operations", "Marketing", "Admin"];

interface SummaryItem { label: AttendanceStatus; color: string; }
const SUMMARY_ITEMS: SummaryItem[] = [
  { label: "Present",     color: "var(--success)" },
  { label: "Late",        color: "var(--warn)"    },
  { label: "Absent",      color: "var(--error)"   },
  { label: "On Leave",    color: "var(--info)"    },
  { label: "Half Day",    color: "var(--primary)" },
  { label: "Weekly Off",  color: "var(--outline)" },
];

export default function AttendanceTab() {
  const [branch, setBranch]   = useState("All Branches");
  const [dept, setDept]       = useState("All Departments");
  const [showImport, setShowImport] = useState(false);

  const filtered = ALL_RECORDS.filter(r =>
    (branch === "All Branches"    || r.branch === branch) &&
    (dept   === "All Departments" || r.department === dept)
  );

  const counts = Object.fromEntries(
    SUMMARY_ITEMS.map(item => [item.label, filtered.filter(r => r.status === item.label).length])
  ) as Record<AttendanceStatus, number>;

  return (
    <>
      {/* Toolbar */}
      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <input type="date" className="field-input" style={{ width: 160 }} defaultValue="2025-06-30" />
        <select className="field-input" style={{ width: 160 }} value={branch} onChange={e => setBranch(e.target.value)}>
          {BRANCHES.map(b => <option key={b}>{b}</option>)}
        </select>
        <select className="field-input" style={{ width: 180 }} value={dept} onChange={e => setDept(e.target.value)}>
          {DEPARTMENTS.map(d => <option key={d}>{d}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        <button className="btn btn-ghost btn-sm">
          <i className="ti ti-download" /> Export CSV
        </button>
        <button className="btn btn-filled btn-sm" onClick={() => setShowImport(true)}>
          <i className="ti ti-upload" /> Import Attendance
        </button>
      </div>

      {/* Summary chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        {SUMMARY_ITEMS.map(item => (
          <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 12px", background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 6, fontSize: 12 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: item.color, flexShrink: 0, display: "inline-block" }} />
            <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{counts[item.label]}</span>
            <span style={{ color: "var(--on-variant)", fontSize: 11 }}>{item.label}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 12px", background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 6, fontSize: 11, marginLeft: "auto", color: "var(--on-variant)" }}>
          Total: {filtered.length} employees
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Branch</th>
                <th>Clock In</th>
                <th>Clock Out</th>
                <th>Total Hrs</th>
                <th>OT</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => {
                const isLateIn = r.clockIn !== "—" && r.clockIn > "09:15";
                return (
                  <tr key={r.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <div style={{ width: 30, height: 30, borderRadius: "50%", background: "rgba(30,78,140,0.1)", color: "var(--primary)", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          {r.initials}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{r.name}</div>
                          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.id}</div>
                        </div>
                      </div>
                    </td>
                    <td>{r.department}</td>
                    <td>{r.branch}</td>
                    <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.clockIn === "—" ? "var(--outline-v)" : isLateIn ? "var(--error)" : "var(--on-bg)" }}>
                      {r.clockIn}
                    </td>
                    <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.clockOut === "—" ? "var(--outline-v)" : "var(--on-bg)" }}>
                      {r.clockOut}
                    </td>
                    <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.totalHours}</td>
                    <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.ot === "—" ? "var(--outline-v)" : "var(--success)" }}>{r.ot}</td>
                    <td><span className={BADGE_MAP[r.status]}>{r.status}</span></td>
                    <td>
                      <button className="btn btn-ghost btn-sm" style={{ padding: "3px 10px", fontSize: 11 }}>View</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {showImport && <ImportModal onClose={() => setShowImport(false)} />}
    </>
  );
}
