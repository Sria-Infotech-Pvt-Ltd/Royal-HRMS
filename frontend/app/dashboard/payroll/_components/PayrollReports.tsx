"use client";

import { useState } from "react";

const REPORTS = [
  {
    category: "Statutory Reports",
    items: [
      { key: "pf",      icon: "ti-building-bank",  title: "PF Report",              desc: "Employee & employer PF contribution summary with UAN mapping",            month: "June 2026", size: "48 KB"  },
      { key: "esi",     icon: "ti-stethoscope",    title: "ESI Report",             desc: "ESI deductions for eligible employees below ₹21,000 threshold",          month: "June 2026", size: "32 KB"  },
      { key: "pt",      icon: "ti-receipt",        title: "PT Report",              desc: "Professional Tax deductions by state and salary slab",                    month: "June 2026", size: "18 KB"  },
      { key: "tds",     icon: "ti-file-certificate", title: "TDS Report (Form 16)", desc: "Monthly TDS deducted per employee with annual projected liability",       month: "June 2026", size: "124 KB" },
    ],
  },
  {
    category: "Payroll Summary",
    items: [
      { key: "register", icon: "ti-table",         title: "Salary Register",        desc: "Detailed salary register with all earnings and deductions for all employees", month: "June 2026", size: "210 KB" },
      { key: "summary",  icon: "ti-chart-bar",     title: "Payroll Summary",        desc: "High-level payroll cost summary by department and employee type",         month: "June 2026", size: "56 KB"  },
      { key: "bank",     icon: "ti-credit-card",   title: "Bank Advice",            desc: "Bank transfer file for NEFT/RTGS bulk salary disbursement",               month: "June 2026", size: "14 KB"  },
      { key: "monthly",  icon: "ti-calendar-stats", title: "Monthly Payroll Report", desc: "Complete monthly payroll report with variance analysis vs prior month",   month: "June 2026", size: "98 KB"  },
    ],
  },
];

type DownloadState = "idle" | "loading" | "done";

export default function PayrollReports() {
  const [states, setStates] = useState<Record<string, DownloadState>>({});

  function download(key: string, type: "pdf" | "excel") {
    const id = `${key}_${type}`;
    setStates(p => ({ ...p, [id]: "loading" }));
    setTimeout(() => setStates(p => ({ ...p, [id]: "done" })), 1000);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-calendar" />
          <select style={{ border: "none", background: "transparent", color: "var(--on-bg)", fontSize: 13 }}>
            <option>June 2026</option>
            <option>May 2026</option>
            <option>Apr 2026</option>
            <option>Mar 2026</option>
          </select>
        </div>
        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-building-skyscraper" />
          <select style={{ border: "none", background: "transparent", color: "var(--on-bg)", fontSize: 13 }}>
            <option>All Branches</option>
            <option>Head Office</option>
            <option>Mumbai</option>
            <option>Chennai</option>
          </select>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-outline btn-sm">
          <i className="ti ti-filter" /> Filter Reports
        </button>
      </div>

      {REPORTS.map(section => (
        <div key={section.category}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            {section.category}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {section.items.map(report => {
              const pdfState   = states[`${report.key}_pdf`]   ?? "idle";
              const xlsxState  = states[`${report.key}_excel`] ?? "idle";
              return (
                <div key={report.key} className="card" style={{ overflow: "visible" }}>
                  <div style={{ padding: "16px 20px" }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                      <div style={{ width: 40, height: 40, borderRadius: "var(--radius)", background: "rgba(30,78,140,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <i className={`ti ${report.icon}`} style={{ fontSize: 20, color: "var(--primary)" }} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>{report.title}</div>
                        <div style={{ fontSize: 12, color: "var(--on-variant)", lineHeight: 1.5, marginBottom: 10 }}>{report.desc}</div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                          <span className="badge badge-primary">{report.month}</span>
                          <span style={{ fontSize: 11, color: "var(--outline)" }}>{report.size}</span>
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            className="btn btn-filled btn-sm"
                            onClick={() => download(report.key, "pdf")}
                          >
                            {pdfState === "loading"
                              ? <><i className="ti ti-loader-2" /> Generating...</>
                              : pdfState === "done"
                              ? <><i className="ti ti-check" /> Downloaded</>
                              : <><i className="ti ti-file-type-pdf" /> Export PDF</>}
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => download(report.key, "excel")}
                          >
                            {xlsxState === "loading"
                              ? <><i className="ti ti-loader-2" /> Generating...</>
                              : xlsxState === "done"
                              ? <><i className="ti ti-check" /> Downloaded</>
                              : <><i className="ti ti-table-export" /> Export Excel</>}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
