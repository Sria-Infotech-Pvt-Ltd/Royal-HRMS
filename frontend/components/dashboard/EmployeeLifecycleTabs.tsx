"use client";

import { useState } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { EmployeeLifecycle, LifecycleEmployee } from "@/types/dashboard";
import NoticePeriodRow from "./NoticePeriodRow";

type Tab = "new_joiners" | "notice_period" | "work_anniversaries";

function resolveName(emp: LifecycleEmployee): string {
  return emp.name ?? emp.full_name ?? emp.employee_name ?? "—";
}

function resolveId(emp: LifecycleEmployee, index: number): string {
  return String(emp.id ?? emp.employee_id ?? index);
}

function initials(emp: LifecycleEmployee): string {
  const n = resolveName(emp);
  if (n === "—") return "?";
  return n.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

function joinDate(emp: LifecycleEmployee): string {
  return emp.join_date ?? emp.joining_date ?? "";
}

function anniversaryDate(emp: LifecycleEmployee): string {
  return emp.anniversary_date ?? emp.date ?? "";
}

function EmployeeRow({ emp, tab }: { emp: LifecycleEmployee; tab: Tab }) {
  const displayName = resolveName(emp);
  if (tab === "notice_period") {
    return (
      <NoticePeriodRow
        fullName={displayName}
        employeeId={emp.employee_id}
        department={emp.department}
        branch={emp.branch}
        approvedAt={emp.approved_at}
        lastWorkingDay={emp.last_working_day ?? emp.last_day}
        daysRemaining={emp.days_remaining}
        noticeStatus={emp.notice_status}
      />
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", borderBottom: "1px solid var(--bg-high)" }}>
      <div style={{
        width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
        background: "var(--primary)", color: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 700,
      }}>
        {initials(emp)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {displayName}
        </div>
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.designation ?? "—"} · {emp.department ?? "—"}</div>
      </div>
      {tab === "new_joiners" && (
        <div style={{ fontSize: 11, color: "var(--success)", fontWeight: 600, whiteSpace: "nowrap" }}>
          <i className="ti ti-calendar-plus" style={{ marginRight: 3 }} />{joinDate(emp)}
        </div>
      )}
      {tab === "work_anniversaries" && (
        <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: "rgba(181,101,29,0.12)", color: "var(--warn)", whiteSpace: "nowrap" }}>
          {emp.years !== undefined ? `${emp.years} ${emp.years === 1 ? "year" : "years"}` : anniversaryDate(emp)}
        </span>
      )}
    </div>
  );
}

export default function EmployeeLifecycleTabs() {
  const [active, setActive] = useState<Tab>("new_joiners");
  const { data, loading } = useFetch<EmployeeLifecycle>(API.dashboard.employeeLifecycle);

  const tabs: { key: Tab; icon: string; label: string }[] = [
    { key: "new_joiners",        icon: "ti-user-plus", label: "New Joiners"    },
    { key: "notice_period",      icon: "ti-logout",    label: "Notice Period"  },
    { key: "work_anniversaries", icon: "ti-award",     label: "Anniversaries"  },
  ];

  const count = (key: Tab) => data?.[key]?.count ?? 0;
  const employees = data?.[active]?.employees ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-arrows-exchange" /> Employee Lifecycle</div>
        <Link href="/dashboard/employees" className="btn btn-ghost btn-sm">All employees</Link>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--bg-high)", padding: "0 16px" }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActive(tab.key)}
            suppressHydrationWarning
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "8px 12px", border: "none", background: "transparent",
              cursor: "pointer", fontSize: 12, fontWeight: active === tab.key ? 700 : 500,
              color: active === tab.key ? "var(--primary)" : "var(--on-variant)",
              borderBottom: active === tab.key ? "2px solid var(--primary)" : "2px solid transparent",
              marginBottom: -1,
              transition: "color 0.15s",
            }}
          >
            <i className={`ti ${tab.icon}`} style={{ fontSize: 12 }} />
            {tab.label}
            {!loading && (
              <span style={{
                fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 10,
                background: active === tab.key ? "rgba(30,78,140,0.12)" : "var(--bg-high)",
                color: active === tab.key ? "var(--primary)" : "var(--on-variant)",
              }}>
                {count(tab.key)}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : employees.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-user" style={{ fontSize: 22, display: "block", marginBottom: 6, opacity: 0.3 }} />
          No records
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {employees.map((emp, index) => (
            <EmployeeRow key={resolveId(emp, index)} emp={emp} tab={active} />
          ))}
        </div>
      )}
    </div>
  );
}
