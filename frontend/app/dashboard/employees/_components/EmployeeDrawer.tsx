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

interface Props {
  employee: Employee;
  onClose:  () => void;
  /** "self" hides the admin-only "Edit full record"/reveal-sensitive controls — used by the ESS "Open full employee profile" view. */
  mode?: "admin" | "self";
}

interface RevealedFields {
  pan_number?:         string;
  account_number?:     string;
  ifsc_code?:          string;
  name_as_per_aadhar?: string;
}

interface EmployeeDetailSensitive {
  work_location?: string;
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
  };
  reporting_manager?: { name: string | null } | null;
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

function SectionTitle({ icon, title }: { icon: string; title: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", marginTop: 22, marginBottom: 10 }}>
      <i className={`ti ${icon}`} /> {title}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{label}</div>
      <div style={{ fontSize: 13, fontFamily: mono ? "Menlo, Consolas, monospace" : undefined }}>{value || "—"}</div>
    </div>
  );
}

export default function EmployeeDrawer({ employee, onClose, mode = "admin" }: Props) {
  const router = useRouter();
  const isAdmin = mode === "admin";
  const canViewPayrollPerm = useDirectoryPermission("payroll.view");
  const canViewSensitive   = useDirectoryPermission("employees.view_sensitive");
  // Viewing your own compensation is never gated behind the "view someone
  // else's payroll" permission — that permission exists to protect OTHER
  // people's pay, not to hide your own from you.
  const canViewPayroll = isAdmin ? canViewPayrollPerm : true;

  const { data: salaryHistory, status: salaryStatus } = useFetch<EmployeeSalaryConfig[]>(
    canViewPayroll ? API.payroll.employeeSalaryHistory(employee.id) : null,
  );
  const currentSalary = (salaryHistory ?? []).find(s => s.is_active) ?? null;

  // The server pre-masks account_number/ifsc_code when viewing someone
  // else's record without employees.view_sensitive, and pan_masked/
  // aadhaar_masked are always safe, already-masked previews — this is the
  // real data, not a hardcoded placeholder.
  const { data: detail } = useFetch<EmployeeDetailSensitive>(API.employees.detail(employee.id));
  const { data: actionHistory } = useFetch<ActionHistoryRow[]>(API.employees.actionHistory(employee.id));
  const p = detail?.profile;

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

  return (
    <div
      className="drawer-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="drawer open" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Avatar text={initials(employee.firstName, employee.lastName)} size={32} color={avatarColor(employee.department)} />
            <span className="drawer-title">{employee.code} · {employee.designation || "—"}</span>
          </div>
          <button className="drawer-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="drawer-body">
          <SectionTitle icon="ti-id-badge-2" title="Personal Details" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Full legal name" value={fullName(employee)} />
            <Field label="Date of birth" value={formatDate(p?.date_of_birth)} />
            <Field label="Gender" value={p?.gender} />
            <Field label="Blood group" value={p?.blood_group} />
            <Field label="Nationality" value={p?.nationality} />
            <Field label="Marital status" value={p?.marital_status} />
          </div>

          <SectionTitle icon="ti-briefcase" title="Employment & Assignment" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Employee number" value={employee.code} />
            <Field label="Position" value={employee.designation} />
            <Field label="Department" value={employee.orgUnitName || employee.department} />
            <Field label="Work location" value={detail?.work_location || employee.location} />
            <Field label="Date of joining" value={formatDate(employee.dateOfJoining)} />
            <Field label="Reporting manager" value={employee.reportingManagerName || detail?.reporting_manager?.name} />
          </div>
          {actionHistory && actionHistory.length > 0 && (
            <div style={{ marginTop: -4, marginBottom: 8 }}>
              <span className="badge badge-warn">{actionHistory[actionHistory.length - 1].status_display}</span>
            </div>
          )}

          <SectionTitle icon="ti-address-book" title="Contact & Address" />
          <div className="form-row cols-2" style={{ marginBottom: 8 }}>
            <Field label="Work email" value={employee.email} />
            <Field label="Personal email" value={null} />
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
                      {formatDate(row.effective_from)} to {row.effective_to === "9999-12-31" ? "present" : formatDate(row.effective_to)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="drawer-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          {isAdmin && (
            <button className="btn btn-filled" onClick={() => router.push(`/dashboard/employees/${employee.id}`)}>
              Edit full record
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
