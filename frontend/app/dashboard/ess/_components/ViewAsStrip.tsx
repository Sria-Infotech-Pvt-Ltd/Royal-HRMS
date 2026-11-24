"use client";

// Shown above the workspace banner while someone is looking at an employee's workspace on their behalf.

import { tr } from "@/lib/i18n/tr";
import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface ViewedEmployee {
  full_name: string;
  employee_id: string;
}

export default function ViewAsStrip() {
  // While viewing, this call answers as the viewed employee.
  const { data: employee, error } = useFetch<ViewedEmployee>(API.employees.me);

  return (
    <div
      role="status"
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap",
        padding: "8px 14px", borderRadius: 12, background: "var(--warn-c)", color: "var(--warn)", fontSize: 12.5, fontWeight: 600,
      }}
    >
      <span>
        <i className="ti ti-eye" style={{ marginRight: 6 }} />
        {error
          // A mistyped or removed employee code: say so, instead of showing "Viewing this employee's workspace" over an empty page.
          ? tr("{error} Check the employee ID, then go back to Employees.", { error })
          : employee ? tr("Viewing {name}'s workspace — read-only. Nothing you do here is saved.", { name: employee.full_name }) : tr("Viewing this employee's workspace — read-only. Nothing you do here is saved.")}
      </span>
      <Link href="/dashboard/employees" style={{ color: "inherit", textDecoration: "underline" }}>
        {tr("Back to Employees")}
      </Link>
    </div>
  );
}
