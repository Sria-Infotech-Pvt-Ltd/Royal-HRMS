"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useDirectoryPermission } from "@/hooks/usePreviewRole";
import { formatDate } from "@/lib/formatDate";
import { fullName, initials, avatarColor, type Employee } from "../_data";
import type { EmployeeSalaryConfig } from "@/types/payroll";
import Avatar from "./Avatar";
import { SectionTitle, Field, PillField, ageYears, STATUS_BADGE } from "./EmployeeDrawerParts";
import EmployeeDrawerLeaveCard from "./EmployeeDrawerLeaveCard";
import EmployeeDrawerAuditTrail, { type AuditTrailRow } from "./EmployeeDrawerAuditTrail";

interface Props {
  employee: Employee;
  onClose:  () => void;
  /** "self" hides the admin-only "Edit full record"/reveal-sensitive controls — used by the ESS "Open full employee profile" view. */
  mode?: "admin" | "self";
  /** Self mode only: routes to the profile-correction request flow (ESS "My Profile" → edit form). Falls back to /dashboard/profile when omitted. */
  onRequestCorrection?: () => void;
}

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
    account_number?: string; // pre-masked server-side when viewing someone else's record
    ifsc_code?:      string; // pre-masked server-side when viewing someone else's record
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

export default function EmployeeDrawer({ employee, onClose, mode = "admin", onRequestCorrection }: Props) {
  const router = useRouter();
  const isAdmin = mode === "admin";
  const isSelf  = mode === "self";
  const canViewPayrollPerm = useDirectoryPermission("payroll.view");
  const canViewSensitive   = useDirectoryPermission("employees.view_sensitive");
  // Viewing your own compensation is never gated behind the "view someone
  // else's payroll" permission — that permission exists to protect OTHER
  // people's pay, not to hide your own from you.
  const canViewPayroll = isAdmin ? canViewPayrollPerm : true;

  // employee.id is only ever empty for an account with no real employee_id
  // (e.g. a System Admin login that was never onboarded as an employee
  // record) — building /employees/<id>/... URLs with an empty id collapses
  // the path and 404s against the wrong route, so every one of these calls
  // is skipped entirely rather than firing a malformed request.
  const hasEmployeeId = !!employee.id;

  const { data: salaryHistory, status: salaryStatus } = useFetch<EmployeeSalaryConfig[]>(
    hasEmployeeId && canViewPayroll ? API.payroll.employeeSalaryHistory(employee.id) : null,
  );
  const currentSalary = (salaryHistory ?? []).find(s => s.is_active) ?? null;

  // The server pre-masks account_number/ifsc_code when viewing someone
  // else's record without employees.view_sensitive, and pan_masked/
  // aadhaar_masked are always safe, already-masked previews — this is the
  // real data, not a hardcoded placeholder.
  const { data: detail } = useFetch<EmployeeDetailSensitive>(hasEmployeeId ? API.employees.detail(employee.id) : null);
  const { data: actionHistory } = useFetch<ActionHistoryRow[]>(hasEmployeeId ? API.employees.actionHistory(employee.id) : null);
  // Self-service views record a real "profile_viewed_self" AuditLog entry
  // server-side every time this call is made (see EmployeeAuditTrailView) —
  // this isn't a read-only fetch of pre-existing data in that mode.
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

  const mouseDownOnOverlay = useRef(false);
  const currentAddress = [p?.current_village, p?.current_district, p?.current_state].filter(Boolean).join(", ");

  const orgUnitName   = detail?.org_unit_name || employee.orgUnitName || employee.department;
  const orgUnitParent = detail?.org_unit_parent_name || employee.orgUnitParentName;
  const departmentValue = orgUnitParent ? `${orgUnitParent} > ${orgUnitName}` : orgUnitName;

  const dobValue = p?.date_of_birth
    ? `${formatDate(p.date_of_birth)}${ageYears(p.date_of_birth) !== null ? ` · ${ageYears(p.date_of_birth)} yrs` : ""}`
    : undefined;

  return (
    <div
      className="drawer-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="drawer open" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Avatar text={initials(employee.firstName, employee.lastName)} size={32} color={avatarColor(employee.department)} photoUrl={employee.photoUrl} />
            <div>
              <div className="drawer-title">{fullName(employee)}</div>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{employee.code} · {employee.designation || "—"}</span>
            </div>
          </div>
          <button className="drawer-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="drawer-body">
          {!hasEmployeeId && (
            <div className="alert alert-info mb-16">
              <i className="ti ti-info-circle" /> This account has no employee record on file (no
              employee number assigned), so employment, pay, statutory, and history details below
              are unavailable. This is expected for an admin/system login that was never onboarded
              as an employee — sign in as an onboarded employee to see a full record.
            </div>
          )}
          <SectionTitle icon="ti-id-badge-2" title="Personal Details" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Full legal name" value={fullName(employee)} />
            <Field label="Date of birth" value={dobValue} />
            <Field label="Gender" value={p?.gender} />
            <Field label="Blood group" value={p?.blood_group} />
            <Field label="Nationality" value={p?.nationality} />
            <Field label="Marital status" value={p?.marital_status} />
          </div>

          <SectionTitle icon="ti-briefcase" title="Employment & Assignment" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Employee number" value={employee.code} />
            <Field label="Position" value={employee.designation} />
            <Field label="Department" value={departmentValue} />
            <Field label="Work location" value={detail?.work_location || employee.location} />
            <Field label="Date of joining" value={formatDate(employee.dateOfJoining)} />
            <Field label="Reporting manager" value={employee.reportingManagerName || detail?.reporting_manager?.name} />
            <PillField label="Status" value={currentStatus} badgeClass={STATUS_BADGE[currentStatus] ?? "badge-neutral"} />
          </div>

          <SectionTitle icon="ti-address-book" title="Contact & Address" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Work email" value={employee.email} />
            <Field label="Personal email" value={p?.personal_email} />
            <Field label="Mobile number" value={employee.phone} />
            <Field label="Current address" value={currentAddress} />
          </div>

          <SectionTitle icon="ti-phone" title="Emergency Contact" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Name" value={p?.emergency_name} />
            <Field label="Relationship" value={p?.emergency_relationship} />
            <Field label="Phone" value={p?.emergency_phone} />
          </div>

          <SectionTitle icon="ti-currency-rupee" title="Basic Pay" />
          {!canViewPayroll ? (
            <div className="alert alert-info" style={{ fontSize: 12 }}>
              <i className="ti ti-lock" /> Compensation is hidden for your role — the payroll.view permission is required to see CTC.
            </div>
          ) : salaryStatus === 403 ? (
            <div className="alert alert-info" style={{ fontSize: 12 }}>
              <i className="ti ti-lock" /> Compensation is hidden for your role.
            </div>
          ) : currentSalary ? (
            <div className="form-row cols-2">
              <Field label="Annual fixed CTC" value={`₹${Number(currentSalary.annual_ctc).toLocaleString("en-IN")}`} />
              {/* Real Position.grade this employee currently holds — no
                  fabricated "L2/01"-style band/sequence exists, so only the
                  actual grade value is shown. */}
              <Field label="Pay scale" value={detail?.position_grade ?? undefined} />
              <Field label="Valid from" value={formatDate(currentSalary.effective_from)} />
            </div>
          ) : (
            <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No CTC on file yet.</p>
          )}

          <SectionTitle icon="ti-shield-lock" title="Government IDs & Bank · Masked" />
          {revealErr && <div className="alert alert-error mb-8" style={{ fontSize: 12 }}>{revealErr}</div>}
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field mono label="PAN" value={revealed?.pan_number || p?.pan_masked} />
            <Field mono label="Aadhaar" value={p?.aadhaar_masked} />
            <Field mono label="Bank account" value={revealed?.account_number || p?.account_number} />
          </div>
          {isAdmin && (
            canViewSensitive ? (
              !revealed && (
                <button className="btn btn-outline btn-sm" disabled={revealing} onClick={handleReveal}>
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
            <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 8 }}>
              This reveal was recorded in the audit log.
            </p>
          )}

          <SectionTitle icon="ti-history" title="Action History" />
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

          <SectionTitle icon="ti-file-shield" title="Consent & Retention" />
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 8 }}>
            {/* No dedicated consent-timestamp field exists on this model —
                reusing the real date-of-joining (when the employee record,
                and therefore this consent, was first captured) rather than
                a fabricated date. Purposes/retention/erasure lines are
                standard statutory record-keeping policy text, not
                per-employee data. */}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ fontSize: 13 }}>Consent captured</div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>Captured digitally · {formatDate(employee.dateOfJoining)}</div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ fontSize: 13 }}>Purposes</div>
              <div style={{ fontSize: 13, fontWeight: 700, textAlign: "right" }}>Payroll, statutory filing, benefits, workplace administration</div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ fontSize: 13 }}>Retention</div>
              <div style={{ fontSize: 13, fontWeight: 700, textAlign: "right" }}>8 years after exit — Income Tax and EPF record-keeping</div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ fontSize: 13 }}>Erasure</div>
              <div style={{ fontSize: 13, fontWeight: 700, textAlign: "right" }}>Non-statutory fields erasable on request; statutory records cannot be deleted early</div>
            </div>
          </div>

          <EmployeeDrawerAuditTrail rows={auditTrail ?? null} />

          {isSelf && <EmployeeDrawerLeaveCard />}
        </div>

        <div className="drawer-footer" style={{ flexDirection: "column", alignItems: "stretch" }}>
          {isSelf && (
            <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "0 0 10px" }}>
              Submit corrections for HR approval. The official employee record changes only after approval.
            </p>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
            {isSelf && (
              <>
                <button className="btn btn-outline" onClick={() => router.push("/dashboard/leave")}>Request leave</button>
                <button className="btn btn-filled" onClick={onRequestCorrection ?? (() => router.push("/dashboard/profile"))}>
                  Request profile correction
                </button>
              </>
            )}
            {isAdmin && (
              <button className="btn btn-filled" onClick={() => router.push(`/dashboard/employees/${employee.id}`)}>
                Edit full record
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
