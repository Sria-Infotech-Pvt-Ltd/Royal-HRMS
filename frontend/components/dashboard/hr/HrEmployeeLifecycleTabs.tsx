"use client";

import { useState } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate as sharedFormatDate } from "@/lib/formatDate";
import type { HREmployeeLifecycle, HRLifecycleEmployee } from "@/types/dashboard";

type Tab = "new_joiners" | "notice_period" | "work_anniversaries";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "new_joiners",        label: "New Joiners",   icon: "ti-user-plus"    },
  { key: "notice_period",      label: "Notice Period", icon: "ti-user-minus"   },
  { key: "work_anniversaries", label: "Anniversaries", icon: "ti-confetti"     },
];

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "—";
  return sharedFormatDate(dateStr);
}

function initials(name: string): string {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

function subLabel(tab: Tab, emp: HRLifecycleEmployee): string {
  if (tab === "new_joiners")        return emp.date_of_joining ? `Joined ${formatDate(emp.date_of_joining)}` : emp.designation ?? "—";
  if (tab === "notice_period")      return emp.date_of_joining ? `Since ${formatDate(emp.date_of_joining)}` : "—";
  if (tab === "work_anniversaries") return emp.years_completed ? `${emp.years_completed} year${emp.years_completed !== 1 ? "s" : ""} · ${formatDate(emp.anniversary_date)}` : formatDate(emp.anniversary_date);
  return "—";
}

export default function HrEmployeeLifecycleTabs() {
  const [activeTab, setActiveTab] = useState<Tab>("new_joiners");
  const { data, loading } = useFetch<HREmployeeLifecycle>(API.dashboard.hrEmployeeLifecycle);

  const group = data?.[activeTab];
  const employees: HRLifecycleEmployee[] = group?.employees ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-users" /> Employee Lifecycle</div>
        {!loading && group && group.count > 0 && (
          <span className="badge badge-primary">{group.count}</span>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, padding: "0 16px", borderBottom: "1px solid var(--border)" }}>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              display: "flex", alignItems: "center", gap: 5, padding: "8px 10px",
              fontSize: 12, fontWeight: 600, border: "none", background: "none", cursor: "pointer",
              color: activeTab === tab.key ? "var(--primary)" : "var(--on-variant)",
              borderBottom: `2px solid ${activeTab === tab.key ? "var(--primary)" : "transparent"}`,
              marginBottom: -1, transition: "color 0.15s",
            }}
          >
            <i className={`ti ${tab.icon}`} style={{ fontSize: 13 }} />
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : employees.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-users" style={{ fontSize: 22, display: "block", marginBottom: 6, opacity: 0.3 }} />
          No records
        </div>
      ) : (
        <div style={{ padding: "8px 0" }}>
          {employees.map((emp, index) => (
            <div key={emp.employee_id ?? index} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 20px" }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                background: "var(--primary)", color: "#fff",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 11, fontWeight: 700,
              }}>
                {initials(emp.full_name)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{emp.full_name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{emp.department}{emp.designation ? ` · ${emp.designation}` : ""}</div>
              </div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", textAlign: "right", whiteSpace: "nowrap", flexShrink: 0 }}>
                {subLabel(activeTab, emp)}
              </div>
            </div>
          ))}
          <div style={{ padding: "8px 20px 4px", borderTop: "1px solid var(--border)" }}>
            <Link href="/dashboard/employees" style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}>
              View all employees <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
