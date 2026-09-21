"use client";

// Landing view for the ESS "My Profile" tab. "View employee record" / "Open
// full employee profile" open the exact same read-only Employee Drawer
// Admin sees from the Employee Directory (self-service mode: no edit/
// reveal-sensitive controls) — matching this page's own subtitle ("The
// same employee record and layout used by Admin"). "Request profile
// correction" is the one real edit surface (ProfileClient), reused as-is.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import EmployeeDrawer from "@/app/dashboard/employees/_components/EmployeeDrawer";
import type { Employee } from "@/app/dashboard/employees/_data";

interface ProfileSummaryData {
  employee_id:      string;
  full_name:        string;
  email:            string;
  phone:            string | null;
  designation:      string;
  department:       string;
  branch:           string;
  date_of_joining:  string | null;
  date_joined:      string | null;
  work_location:    string | null;
  profile:          { date_of_birth: string | null } | null;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return formatDate(d);
}

function toDrawerEmployee(d: ProfileSummaryData): Employee {
  const [firstName, ...rest] = (d.full_name || "").split(" ");
  return {
    id: d.employee_id, code: d.employee_id,
    firstName: firstName || "", middleName: "", lastName: rest.join(" "),
    email: d.email, phone: d.phone ?? "",
    department: d.department, designation: d.designation,
    dateOfJoining: d.date_of_joining ?? d.date_joined ?? "", dateOfBirth: "",
    location: d.branch, gender: "male",
    status: "active", employmentStatus: "probation", confirmationDate: null,
    details: {}, tables: {},
  };
}

interface Props {
  onOpenFullProfile: () => void;
}

export default function ProfileSummaryTab({ onOpenFullProfile }: Props) {
  const { data } = useFetch<ProfileSummaryData>(API.employees.me);
  const [showRecord, setShowRecord] = useState(false);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My profile</div>
          <div className="page-sub">The same employee record and layout used by Admin, with self-service permissions.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowRecord(true)}>Open full employee profile</button>
        </div>
      </div>

      <div className="card mb-16">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Profile controls</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review your official record or request an approved correction.</div>
        </div>
        <div style={{ padding: "12px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <button
            type="button"
            onClick={() => setShowRecord(true)}
            style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
          >
            <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>View employee record</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Personal, employment, pay, statutory, leave and audit details</div>
          </button>
          <button
            type="button"
            onClick={onOpenFullProfile}
            style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
          >
            <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Request profile correction</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Submit changes to contact, address or personal information</div>
          </button>
        </div>
      </div>

      <div className="card">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>My record at a glance</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review official fields, then open the full record for all sections.</div>
        </div>
        <div style={{ padding: "4px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>EMPLOYEE ID</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.employee_id ?? "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF BIRTH</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{fmtDate(data?.profile?.date_of_birth)}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF JOINING</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{fmtDate(data?.date_of_joining ?? data?.date_joined)}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>WORK LOCATION</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.work_location || "—"}</div>
          </div>
        </div>
      </div>

      {showRecord && data && (
        <EmployeeDrawer employee={toDrawerEmployee(data)} mode="self" onClose={() => setShowRecord(false)} />
      )}
    </div>
  );
}
