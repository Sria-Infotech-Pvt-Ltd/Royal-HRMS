"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle } from "@/types/payroll";

interface PagedResponse<T> { results: T[]; count: number; }
interface Branch { id: string; branch_name: string; branch_code: string; }

const REPORTS = [
  {
    category: "Statutory Reports",
    items: [
      { key: "pf",   icon: "ti-building-bank",    title: "PF Report",               desc: "Employee & employer PF contribution summary with UAN mapping" },
      { key: "esi",  icon: "ti-stethoscope",       title: "ESI Report",              desc: "ESI deductions for eligible employees below the statutory threshold" },
      { key: "pt",   icon: "ti-receipt",           title: "PT Report",               desc: "Professional Tax deductions by state and salary slab" },
      { key: "tds",  icon: "ti-file-certificate",  title: "TDS (Form 16)",           desc: "Monthly TDS deducted per employee with annual projected liability" },
    ],
  },
  {
    category: "Payroll Summary",
    items: [
      { key: "register", icon: "ti-table",          title: "Salary Register",        desc: "Detailed salary register with all earnings and deductions" },
      { key: "summary",  icon: "ti-chart-bar",      title: "Payroll Summary",        desc: "High-level payroll cost summary by department and employee type" },
      { key: "bank",     icon: "ti-credit-card",    title: "Bank Advice",            desc: "Bank transfer file for NEFT/RTGS bulk salary disbursement" },
      { key: "monthly",  icon: "ti-calendar-stats", title: "Monthly Payroll Report", desc: "Complete monthly payroll report with variance analysis vs prior month" },
    ],
  },
];

export default function PayrollReports() {
  const [selectedCycle, setSelectedCycle] = useState<string>("");
  const [selectedBranch, setSelectedBranch] = useState<string>("");

  const { data: cyclesPage } = useFetch<PagedResponse<PayrollCycle>>(API.payroll.cycles);
  const { data: branchPage  } = useFetch<PagedResponse<Branch>>(API.branches.list);

  const cycles   = cyclesPage?.results ?? [];
  const branches = branchPage?.results ?? [];

  const paidCycles = cycles.filter(c => ["paid", "closed", "payslips_generated", "query_window_open"].includes(c.status));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-calendar" />
          <select
            value={selectedCycle}
            onChange={e => setSelectedCycle(e.target.value)}
            style={{ border: "none", background: "transparent", color: "var(--on-bg)", fontSize: 13 }}
          >
            <option value="">All Periods</option>
            {cycles.map(c => (
              <option key={c.id} value={c.id}>
                {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
              </option>
            ))}
          </select>
        </div>

        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-building-skyscraper" />
          <select
            value={selectedBranch}
            onChange={e => setSelectedBranch(e.target.value)}
            style={{ border: "none", background: "transparent", color: "var(--on-bg)", fontSize: 13 }}
          >
            <option value="">All Branches</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>{b.branch_name}</option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1 }} />
      </div>

      {/* No paid cycles warning */}
      {paidCycles.length === 0 && cycles.length > 0 && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <span>Reports are available after a payroll cycle is completed and payslips are dispatched. Complete a payroll run first.</span>
        </div>
      )}

      {cycles.length === 0 && (
        <div className="alert alert-info">
          <i className="ti ti-info-circle" />
          <span>No payroll cycles yet. Run your first payroll to generate reports.</span>
        </div>
      )}

      {/* Report sections */}
      {REPORTS.map(section => (
        <div key={section.category}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            {section.category}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {section.items.map(report => (
              <div key={report.key} className="card">
                <div style={{ padding: "16px 20px" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                    <div style={{ width: 40, height: 40, borderRadius: "var(--radius)", background: "rgba(30,78,140,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <i className={`ti ${report.icon}`} style={{ fontSize: 20, color: "var(--primary)" }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{report.title}</div>
                      <div style={{ fontSize: 12, color: "var(--on-variant)", lineHeight: 1.5, marginBottom: 12 }}>{report.desc}</div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button className="btn btn-filled btn-sm" disabled>
                          <i className="ti ti-file-type-pdf" /> Export PDF
                        </button>
                        <button className="btn btn-ghost btn-sm" disabled>
                          <i className="ti ti-table-export" /> Export Excel
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

    </div>
  );
}
