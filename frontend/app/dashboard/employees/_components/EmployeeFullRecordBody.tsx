"use client";

// Every real field/section EmployeeDrawer.tsx renders, extracted so it can
// be shown inline on a page (ESS "My Profile") as well as inside the
// slide-in drawer (Admin Employee Directory) — same data-fetching, same
// fields, just without the drawer's own overlay/header/footer chrome.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { formatDateSlash } from "@/lib/formatDate";
import { directoryStatusLabel, fullName, type Employee } from "../_data";
import type { EmployeeSalaryConfig } from "@/types/payroll";
import { SectionCard, Row, ageYears, titleCase, STATUS_CHIP } from "./EmployeeDrawerParts";
import EmployeeDrawerLeaveCard from "./EmployeeDrawerLeaveCard";
import EmployeeDrawerActions from "./EmployeeDrawerActions";
import type { PersonnelActionRequest } from "@/types/personnelAction";
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
    current_address?: string;
    current_village?: string;
    current_district?: string;
    current_state?:   string;
    current_pin_code?: string;
    emergency_name?:         string;
    emergency_relationship?: string;
    emergency_phone?:        string;
    pan_masked?:     string;
    aadhaar_masked?: string;
    account_number?: string;
    ifsc_code?:      string;
    personal_email?: string;
    bank_change_status?: string;
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
  const canViewPayrollPerm = usePermission("payroll.view");
  const canViewSensitive   = usePermission("employees.view_sensitive");
  const canViewLeave       = usePermission("leave.view");
  const canViewPayroll = isAdmin ? canViewPayrollPerm : true;

  const hasEmployeeId = !!employee.id;

  const { data: salaryHistory, status: salaryStatus, refetch: refetchSalary } = useFetch<EmployeeSalaryConfig[]>(
    hasEmployeeId && canViewPayroll ? API.payroll.employeeSalaryHistory(employee.id) : null,
  );
  const currentSalary = (salaryHistory ?? []).find(s => s.is_active) ?? null;

  const { data: detail, refetch: refetchDetail } = useFetch<EmployeeDetailSensitive>(hasEmployeeId ? API.employees.detail(employee.id) : null);
  const { data: actionHistory } = useFetch<ActionHistoryRow[]>(hasEmployeeId ? API.employees.actionHistory(employee.id) : null);
  // Requests raised for this employee that have not (yet) taken effect — shown in
  // Action history with their approval state, as the reference does.
  const { data: requestsPage, refetch: refetchRequests } = useFetch<{ results: PersonnelActionRequest[] }>(
    hasEmployeeId && isAdmin ? API.employees.actionRequests(employee.id) : null,
  );
  const openRequests = (requestsPage?.results ?? []).filter(r => r.status === "pending" || r.status === "failed" || r.status === "rejected").slice(0, 5);
  const { data: auditTrail, status: auditStatus, loading: auditLoading } = useFetch<AuditTrailRow[]>(hasEmployeeId ? API.employees.auditTrail(employee.id) : null);
  const p = detail?.profile;
  const directoryStatus = directoryStatusLabel(employee);

  const [revealed, setRevealed]   = useState<RevealedFields | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [revealErr, setRevealErr] = useState<string | null>(null);
  const [bankDeciding, setBankDeciding] = useState(false);
  const [bankDecideErr, setBankDecideErr] = useState<string | null>(null);

  async function decideBankChange(decision: "approve" | "reject") {
    setBankDeciding(true);
    setBankDecideErr(null);
    try {
      await clientApi.post(API.employees.bankChangeReview(employee.id, decision));
      await refetchDetail();
    } catch (err: unknown) {
      setBankDecideErr((err as { message?: string })?.message ?? "Failed to record decision.");
    } finally {
      setBankDeciding(false);
    }
  }

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

  const addressLine = [p?.current_address, p?.current_village || p?.current_district, p?.current_state].filter(Boolean).join(", ");
  const currentAddress = addressLine && p?.current_pin_code ? `${addressLine} – ${p.current_pin_code}` : addressLine;
  const orgUnitName   = detail?.org_unit_name || employee.orgUnitName || employee.department;
  const orgUnitParent = detail?.org_unit_parent_name || employee.orgUnitParentName;
  const departmentValue = orgUnitParent ? `${orgUnitName} › ${orgUnitParent}` : orgUnitName;

  const dobValue = p?.date_of_birth
    ? `${formatDateSlash(p.date_of_birth)}${ageYears(p.date_of_birth) !== null ? ` · ${ageYears(p.date_of_birth)} yrs` : ""}`
    : undefined;
  // Show the account number masked until it is explicitly revealed (the card is titled "Masked").
  const accountValue = revealed?.account_number || (p?.account_number ? `••••${p.account_number.replace(/•/g, "").slice(-4)}` : undefined);
  const payScale = detail?.position_grade
    ? `${detail.position_grade} / ${String(salaryHistory?.length ?? 1).padStart(2, "0")}`
    : undefined;

  return (
    <div className="emp-record">
      {!hasEmployeeId && (
        <div className="alert alert-info mb-16">
          <i className="ti ti-info-circle" /> This account has no employee record on file (no
          employee number assigned), so employment, pay, statutory, and history details below
          are unavailable. This is expected for an admin/system login that was never onboarded
          as an employee — sign in as an onboarded employee to see a full record.
        </div>
      )}

      <div className="emp-record-grid">
        <SectionCard title="Personal Details">
          <Row label="Full legal name" value={fullName(employee)} />
          <Row label="Date of birth" value={dobValue} />
          <Row label="Gender" value={titleCase(p?.gender)} />
          <Row label="Blood group" value={p?.blood_group} />
          <Row label="Nationality" value={p?.nationality} />
          <Row label="Marital status" value={titleCase(p?.marital_status)} />
        </SectionCard>

        <SectionCard title="Employment & Assignment">
          <Row label="Employee number" value={employee.code} />
          <Row label="Position" value={employee.designation} />
          <Row label="Department" value={departmentValue} />
          <Row label="Work location" value={detail?.work_location || employee.location} />
          <Row label="Date of joining" value={formatDateSlash(employee.dateOfJoining)} />
          <Row label="Reporting manager" value={employee.reportingManagerName || detail?.reporting_manager?.name || "CEO Office"} />
          <Row
            label="Status"
            valueNode={<span className={`chip ${STATUS_CHIP[directoryStatus] ?? ""}`}>{directoryStatus}</span>}
          />
        </SectionCard>

        <SectionCard title="Contact & Address">
          <Row label="Work email" value={employee.email} />
          <Row label="Personal email" value={p?.personal_email} />
          <Row label="Mobile number" value={employee.phone} />
          <Row label="Current address" value={currentAddress} />
        </SectionCard>

        <SectionCard title="Emergency Contact">
          <Row label="Name" value={p?.emergency_name} />
          <Row label="Relationship" value={p?.emergency_relationship} />
          <Row label="Phone" value={p?.emergency_phone} />
        </SectionCard>

        <SectionCard title="Basic Pay">
          {!canViewPayroll || salaryStatus === 403 ? (
            <Row label="Visibility" value="Permission required" />
          ) : currentSalary ? (
            <>
              <Row label="Annual fixed CTC" value={`₹${Number(currentSalary.annual_ctc).toLocaleString("en-IN")}`} />
              <Row label="Pay scale" value={payScale} />
              <Row label="Valid from" value={`${formatDateSlash(currentSalary.effective_from)} → 31/12/9999`} />
            </>
          ) : (
            <Row label="Annual fixed CTC" value="No CTC on file yet." />
          )}
        </SectionCard>

        <SectionCard title="Government IDs & Bank · Masked">
          {revealErr && <div className="alert alert-error mb-8" style={{ fontSize: 12 }}>{revealErr}</div>}
          {isAdmin && !canViewSensitive ? (
            <>
              <Row label="PAN" value="Permission required" />
              <Row label="Aadhaar" value="Permission required" />
              <Row label="Bank account" value="Permission required" />
            </>
          ) : (
            <>
              <Row mono label="PAN" value={revealed?.pan_number || p?.pan_masked} />
              <Row mono label="Aadhaar" value={p?.aadhaar_masked} />
              <Row mono label="Bank account" value={accountValue} />
            </>
          )}
          {isAdmin && p?.bank_change_status === "pending" && (
            <div style={{
              marginTop: 8, padding: "0.75rem", borderRadius: 10,
              background: "var(--warn-bg)", color: "var(--warn)", fontSize: 12,
            }}>
              <div style={{ marginBottom: 8 }}>
                This employee submitted a bank detail change awaiting your review — their
                previous details remain active for payroll until you decide.
              </div>
              {bankDecideErr && <div style={{ color: "var(--crit)", marginBottom: 8 }}>{bankDecideErr}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="rvbtn pri" disabled={bankDeciding} onClick={() => decideBankChange("approve")}>
                  {bankDeciding ? <i className="ti ti-loader-2 animate-spin" /> : <i className="ti ti-check" />} Approve
                </button>
                <button className="rvbtn" disabled={bankDeciding} onClick={() => decideBankChange("reject")}>
                  <i className="ti ti-x" /> Reject
                </button>
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard title="Action History" list={false}>
        {!actionHistory || actionHistory.length === 0 ? (
          <p className="hint">No lifecycle events on record yet.</p>
        ) : (
          actionHistory.map((row, i) => (
            <div key={i} className={`actrow${row.is_current ? " live" : ""}`}>
              <span className="bar" />
              <div className="meta">
                <div className="t1">
                  {row.action_type}
                  {row.is_current && <span className="chip ok">Current</span>}
                </div>
                <div className="t2">
                  {[row.reason_display, row.position_title, row.org_unit_name, row.status_display].filter(Boolean).join(" · ")}
                </div>
              </div>
              <div className="dates" style={{ textAlign: "right" }}>
                {formatDateSlash(row.effective_from)}
                <div className="actdel">to {formatDateSlash(row.effective_to)}</div>
              </div>
            </div>
          ))
        )}
        {openRequests.map(r => (
          <div key={r.id} className="actrow future">
            <span className="bar" />
            <div className="meta">
              <div className="t1">
                {r.action_label}
                <span className={`chip ${r.status === "pending" ? "warn" : "crit"}`}>{r.status_display}</span>
              </div>
              <div className="t2">
                Raised by {r.raised_by_name} · Approver: {r.status === "pending" ? r.current_step_label : r.route}
                {r.status === "rejected" && r.decision_note ? ` · ${r.decision_note}` : ""}
                {r.status === "failed" && r.apply_error ? ` · ${r.apply_error}` : ""}
              </div>
            </div>
            <div className="dates" style={{ textAlign: "right" }}>
              <div className="actdel">effective {formatDateSlash(r.effective_from)}</div>
            </div>
          </div>
        ))}
      </SectionCard>

      {isAdmin && canViewSensitive && (
        <SectionCard title="Sensitive Data Control" list={false}>
          {revealErr && <div className="alert alert-error mb-8" style={{ fontSize: 12 }}>{revealErr}</div>}
          {!revealed ? (
            <button className="rvbtn" disabled={revealing} onClick={handleReveal}>
              {revealing && <i className="ti ti-loader-2 animate-spin" />} Reveal full values
            </button>
          ) : (
            <p className="hint">Full values are now shown in the Government IDs &amp; Bank card above.</p>
          )}
          <div className="hint" style={{ marginTop: 7 }}>Every reveal is written to the audit log under the DPDP Act 2023.</div>
        </SectionCard>
      )}

      <SectionCard title="Consent & Retention">
        <Row label="Consent captured" value={`Captured digitally · ${formatDateSlash(employee.dateOfJoining)}`} />
        <Row label="Purposes" value="Payroll, statutory filing, benefits, workplace administration" />
        <Row label="Retention" value="8 years after exit — Income Tax and EPF record-keeping" />
        <Row label="Erasure" value="Non-statutory fields erasable on request; statutory records cannot be deleted early" />
      </SectionCard>

      <EmployeeDrawerAuditTrail rows={auditTrail ?? null} forbidden={auditStatus === 403} loading={auditLoading} />

      {isSelf && <EmployeeDrawerLeaveCard />}
      {isAdmin && hasEmployeeId && canViewLeave && <EmployeeDrawerLeaveCard employeeCode={employee.id} />}

      {isAdmin && hasEmployeeId && (
        <EmployeeDrawerActions
          employee={employee}
          isExited={!employee.id || employee.status === "inactive"}
          onChanged={() => { refetchRequests(); refetchDetail(); refetchSalary(); }}
        />
      )}
    </div>
  );
}
