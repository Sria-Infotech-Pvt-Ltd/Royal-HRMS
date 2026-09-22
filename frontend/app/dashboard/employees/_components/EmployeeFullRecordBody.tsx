"use client";

// Every real field/section EmployeeDrawer.tsx renders, extracted so it can
// be shown inline on a page (ESS "My Profile") as well as inside the
// slide-in drawer (Admin Employee Directory) — same data-fetching, same
// fields, just without the drawer's own overlay/header/footer chrome.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useDirectoryPermission } from "@/hooks/usePreviewRole";
import { formatDate } from "@/lib/formatDate";
import { fullName, type Employee } from "../_data";
import type { EmployeeSalaryConfig } from "@/types/payroll";
import { SectionCard, Row, ageYears, STATUS_BADGE } from "./EmployeeDrawerParts";
import EmployeeDrawerLeaveCard from "./EmployeeDrawerLeaveCard";
import EmployeeDrawerAuditTrail, { type AuditTrailRow } from "./EmployeeDrawerAuditTrail";

interface RevealedFields {
  pan_number?:         string;
  account_number?:     string;
  ifsc_code?:          string;
  name_as_per_aadhar?: string;
}

interface EmployeeDetailSensitive {
  work_location?: string;
  org_unit_name?: string | null;
  org_unit_parent_name?: string | null;
  profile?: {
    date_of_birth?:  string;
    gender?:         string;
    blood_group?:    string;
    marital_status?: string;
    nationality?:    string;
    current_village?: string;
    current_district?: string;
    current_state?:   string;
    emergency_name?:         string;
    emergency_relationship?: string;
    emergency_phone?:        string;
    pan_masked?:     string;
    aadhaar_masked?: string;
    account_number?: string;
    ifsc_code?:      string;
    personal_email?: string;
  };
  reporting_manager?: { name: string | null } | null;
  position_grade?: string | null;
}

interface ActionHistoryRow {
  action_type: string;
  reason_display: string;
  position_title: string;
  org_unit_name: string;
  status_display: string;
  effective_from: string;
  effective_to: string;
  is_current: boolean;
}

interface Props {
  employee: Employee;
  /** "self" hides admin-only reveal-sensitive controls and shows the Leave card. */
  mode?: "admin" | "self";
}

export default function EmployeeFullRecordBody({ employee, mode = "admin" }: Props) {
  const isAdmin = mode === "admin";
  const isSelf  = mode === "self";
  const canViewPayrollPerm = useDirectoryPermission("payroll.view");
  const canViewSensitive   = useDirectoryPermission("employees.view_sensitive");
  const canViewPayroll = isAdmin ? canViewPayrollPerm : true;

  const hasEmployeeId = !!employee.id;

  const { data: salaryHistory, status: salaryStatus } = useFetch<EmployeeSalaryConfig[]>(
    hasEmployeeId && canViewPayroll ? API.payroll.employeeSalaryHistory(employee.id) : null,
  );
  const currentSalary = (salaryHistory ?? []).find(s => s.is_active) ?? null;

  const { data: detail } = useFetch<EmployeeDetailSensitive>(hasEmployeeId ? API.employees.detail(employee.id) : null);
  const { data: actionHistory } = useFetch<ActionHistoryRow[]>(hasEmployeeId ? API.employees.actionHistory(employee.id) : null);
  const { data: auditTrail } = useFetch<AuditTrailRow[]>(hasEmployeeId ? API.employees.auditTrail(employee.id) : null);
  const p = detail?.profile;
  const currentStatus = actionHistory && actionHistory.length > 0 ? actionHistory[actionHistory.length - 1].status_display : "";

  const [revealed, setRevealed]   = useState<RevealedFields | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [revealErr, setRevealErr] = useState<string | null>(null);

  async function handleReveal() {
    setRevealing(true);
    setRevealErr(null);
    try {
      const { data } = await clientApi.post<{ data: RevealedFields }>(
        API.employees.revealSensitive(employee.id),
        { fields: ["pan_number", "account_number", "ifsc_code", "name_as_per_aadhar"] },
      );
      setRevealed(data.data ?? {});
    } catch (err: unknown) {
      setRevealErr((err as { message?: string })?.message ?? "Could not reveal these fields.");
    } finally {
      setRevealing(false);
    }
  }

  const currentAddress = [p?.current_village, p?.current_district, p?.current_state].filter(Boolean).join(", ");
  const orgUnitName   = detail?.org_unit_name || employee.orgUnitName || employee.department;
  const orgUnitParent = detail?.org_unit_parent_name || employee.orgUnitParentName;
  const departmentValue = orgUnitParent ? `${orgUnitParent} > ${orgUnitName}` : orgUnitName;

  const dobValue = p?.date_of_birth
    ? `${formatDate(p.date_of_birth)}${ageYears(p.date_of_birth) !== null ? ` · ${ageYears(p.date_of_birth)} yrs` : ""}`
    : undefined;

  return (
    <div>
      {!hasEmployeeId && (
        <div className="alert alert-info mb-16">
          <i className="ti ti-info-circle" /> This account has no employee record on file (no
          employee number assigned), so employment, pay, statutory, and history details below
          are unavailable. This is expected for an admin/system login that was never onboarded
          as an employee — sign in as an onboarded employee to see a full record.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <SectionCard icon="ti-id-badge-2" title="Personal Details">
          <Row label="Full legal name" value={fullName(employee)} />
          <Row label="Date of birth" value={dobValue} />
          <Row label="Gender" value={p?.gender} />
          <Row label="Blood group" value={p?.blood_group} />
          <Row label="Nationality" value={p?.nationality} />
          <Row label="Marital status" value={p?.marital_status} />
        </SectionCard>

        <SectionCard icon="ti-briefcase" title="Employment & Assignment">
          <Row label="Employee number" value={employee.code} />
          <Row label="Position" value={employee.designation} />
          <Row label="Department" value={departmentValue} />
          <Row label="Work location" value={detail?.work_location || employee.location} />
          <Row label="Date of joining" value={formatDate(employee.dateOfJoining)} />
          <Row label="Reporting manager" value={employee.reportingManagerName || detail?.reporting_manager?.name} />
          <Row
            label="Status"
            valueNode={currentStatus ? <span className={`badge ${STATUS_BADGE[currentStatus] ?? "badge-neutral"}`}>{currentStatus}</span> : undefined}
          />
        </SectionCard>

        <SectionCard icon="ti-address-book" title="Contact & Address">
          <Row label="Work email" value={employee.email} />
          <Row label="Personal email" value={p?.personal_email} />
          <Row label="Mobile number" value={employee.phone} />
          <Row label="Current address" value={currentAddress} />
        </SectionCard>

        <SectionCard icon="ti-phone" title="Emergency Contact">
          <Row label="Name" value={p?.emergency_name} />
          <Row label="Relationship" value={p?.emergency_relationship} />
          <Row label="Phone" value={p?.emergency_phone} />
        </SectionCard>

        <SectionCard icon="ti-currency-rupee" title="Basic Pay">
          {!canViewPayroll ? (
            <p style={{ fontSize: 12, color: "var(--on-variant)" }}>
              <i className="ti ti-lock" /> Compensation is hidden for your role — the payroll.view permission is required to see CTC.
            </p>
          ) : salaryStatus === 403 ? (
            <p style={{ fontSize: 12, color: "var(--on-variant)" }}>
              <i className="ti ti-lock" /> Compensation is hidden for your role.
            </p>
          ) : currentSalary ? (
            <>
              <Row label="Annual fixed CTC" value={`₹${Number(currentSalary.annual_ctc).toLocaleString("en-IN")}`} />
              <Row label="Pay scale" value={detail?.position_grade ?? undefined} />
              <Row label="Valid from" value={formatDate(currentSalary.effective_from)} />
            </>
          ) : (
            <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No CTC on file yet.</p>
          )}
        </SectionCard>

        <SectionCard icon="ti-shield-lock" title="Government IDs & Bank · Masked">
          {revealErr && <div className="alert alert-error mb-8" style={{ fontSize: 12 }}>{revealErr}</div>}
          <Row mono label="PAN" value={revealed?.pan_number || p?.pan_masked} />
          <Row mono label="Aadhaar" value={p?.aadhaar_masked} />
          <Row mono label="Bank account" value={revealed?.account_number || p?.account_number} />
          {isAdmin && (
            canViewSensitive ? (
              !revealed && (
                <button className="btn btn-outline btn-sm" disabled={revealing} onClick={handleReveal} style={{ marginTop: 4, alignSelf: "flex-start" }}>
                  {revealing ? <i className="ti ti-loader-2 animate-spin" /> : <i className="ti ti-eye" />} Reveal full values
                </button>
              )
            ) : (
              <p style={{ fontSize: 11, color: "var(--on-variant)" }}>
                Masked values shown above are placeholders — revealing the real ones requires the employees.view_sensitive permission.
              </p>
            )
          )}
          {revealed && (
            <p style={{ fontSize: 11, color: "var(--on-variant)" }}>
              This reveal was recorded in the audit log.
            </p>
          )}
        </SectionCard>
      </div>

      <SectionCard icon="ti-history" title="Action History">
        {!actionHistory || actionHistory.length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No lifecycle events on record yet.</p>
        ) : (
          <div className="timeline">
            {actionHistory.map((row, i) => (
              <div key={i} className="tl-item">
                <div className="tl-dot tl-neutral"><i className="ti ti-point" /></div>
                <div className="tl-body" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                  <div>
                    <div className="tl-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {row.action_type}
                      {row.is_current && <span className="badge badge-success" style={{ fontSize: 10 }}>Current</span>}
                    </div>
                    <div className="tl-desc">
                      {[row.reason_display, row.position_title, row.org_unit_name, row.status_display].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
                    {formatDate(row.effective_from)} to {formatDate(row.effective_to)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard icon="ti-file-shield" title="Consent & Retention">
        <Row label="Consent captured" value={`Captured digitally · ${formatDate(employee.dateOfJoining)}`} />
        <Row label="Purposes" value="Payroll, statutory filing, benefits, workplace administration" />
        <Row label="Retention" value="8 years after exit — Income Tax and EPF record-keeping" />
        <Row label="Erasure" value="Non-statutory fields erasable on request; statutory records cannot be deleted early" />
      </SectionCard>

      <EmployeeDrawerAuditTrail rows={auditTrail ?? null} />

      {isSelf && <EmployeeDrawerLeaveCard />}
    </div>
  );
}
