"use client";

// Shown above the workspace banner while someone is looking at an employee's workspace on their behalf.

import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { adminProfilePath } from "@/lib/viewAs";

interface ViewedEmployee {
  full_name: string;
  employee_id: string;
}

export default function ViewAsStrip() {
  // While viewing, this call answers as the viewed employee.
  const { data: employee } = useFetch<ViewedEmployee>(API.employees.me);

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
        Viewing {employee ? `${employee.full_name}'s` : "this employee's"} workspace — read-only. Nothing you do here is saved.
      </span>
      {employee && (
        <Link href={adminProfilePath(employee.employee_id)} style={{ color: "inherit", textDecoration: "underline" }}>
          Admin profile (edit, salary, actions)
        </Link>
      )}
    </div>
  );
}
