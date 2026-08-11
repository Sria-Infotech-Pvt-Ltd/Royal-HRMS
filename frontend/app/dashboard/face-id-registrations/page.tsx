"use client";

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import {
  useFaceRegistrationEmployeePicker,
  useEmployeeFaceStatus,
} from "@/hooks/useHRFaceRegistration";
import HRFaceCaptureModal from "./_components/HRFaceCaptureModal";
import type { FaceRegistrationEmployee, FaceRegistrationStatus } from "@/types/faceRegistration";

const STATUS_BADGE: Record<FaceRegistrationStatus, { label: string; cls: string }> = {
  approved: { label: "Approved", cls: "badge-success" },
  pending:  { label: "Pending",  cls: "badge-warn" },
  rejected: { label: "Rejected", cls: "badge-error" },
};

function StatusBadge({ status }: { status: FaceRegistrationStatus | undefined }) {
  if (!status) return <span className="badge badge-neutral">Not registered</span>;
  const meta = STATUS_BADGE[status];
  return <span className={`badge ${meta.cls}`}>{meta.label}</span>;
}

export default function FaceIdRegistrationsPage() {
  const canRegister = usePermission("facial_recognition.approve");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<FaceRegistrationEmployee | null>(null);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [showCapture, setShowCapture] = useState(false);

  const { employees, loading: loadingEmployees, error: employeesError } = useFaceRegistrationEmployeePicker(search);
  const { status, loading: loadingStatus, error: statusError, refetch: refetchStatus } = useEmployeeFaceStatus(selected?.uuid ?? null);

  if (!canRegister) {
    return (
      <div className="empty-state">
        <i className="ti ti-lock" />
        <h3>You don&apos;t have permission to manage face ID registrations</h3>
        <p>Contact an HR administrator if you believe this is a mistake.</p>
      </div>
    );
  }

  function selectEmployee(employee: FaceRegistrationEmployee) {
    setSelected(employee);
    setConfirmReplace(false);
  }

  function handleRegisterClick() {
    if (status?.status === "approved") {
      setConfirmReplace(true);
      return;
    }
    setShowCapture(true);
  }

  function handleRegistered() {
    refetchStatus();
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Face ID Registrations</div>
          <div className="page-sub">Register or update an employee&apos;s face ID in person — approved immediately.</div>
        </div>
      </div>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* Employee picker */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><i className="ti ti-users" />Employees</span>
          </div>
          <div className="card-body" style={{ padding: 12 }}>
            <div style={{ position: "relative", marginBottom: 10 }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 14, pointerEvents: "none" }} />
              <input
                className="field-input"
                style={{ paddingLeft: 32 }}
                placeholder="Search by name, email or ID…"
                aria-label="Search employees by name, email or ID"
                value={search}
                onChange={e => setSearch(e.target.value)}
                suppressHydrationWarning
              />
            </div>

            {employeesError && (
              <div className="alert alert-error" style={{ marginBottom: 10 }}>
                <i className="ti ti-alert-circle" /><div>{employeesError}</div>
              </div>
            )}

            <div style={{ maxHeight: 480, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
              {loadingEmployees && (
                <div style={{ padding: 20, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                  <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading…
                </div>
              )}
              {!loadingEmployees && employees.length === 0 && (
                <div style={{ padding: 20, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                  No employees match.
                </div>
              )}
              {employees.map((e, idx) => (
                <button
                  key={e.uuid}
                  onClick={() => selectEmployee(e)}
                  style={{
                    width: "100%", textAlign: "left", display: "flex", flexDirection: "column",
                    gap: 2, padding: "9px 12px", cursor: "pointer", border: "none",
                    borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                    background: selected?.uuid === e.uuid ? "var(--primary-c, rgba(30,78,140,0.07))" : "transparent",
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{e.full_name}</span>
                  <span style={{ fontSize: 11, color: "var(--on-variant)" }}>
                    {e.employee_id} · {e.email}{e.branch ? ` · ${e.branch}` : ""}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Selected employee panel */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><i className="ti ti-face-id" />Face ID Status</span>
          </div>
          <div className="card-body" style={{ padding: 16 }}>
            {!selected && (
              <div style={{ color: "var(--on-variant)", fontSize: 13, textAlign: "center", padding: "24px 0" }}>
                Select an employee to view or register their face ID.
              </div>
            )}

            {selected && (
              <>
                {statusError && (
                  <div className="alert alert-error" style={{ marginBottom: 16 }}>
                    <i className="ti ti-alert-circle" /><div>{statusError}</div>
                  </div>
                )}

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "var(--on-bg)" }}>{selected.full_name}</div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                      {selected.employee_id} · {selected.email}
                      {selected.department ? ` · ${selected.department}` : ""}
                      {selected.designation ? ` · ${selected.designation}` : ""}
                    </div>
                  </div>
                  {!loadingStatus && <StatusBadge status={status?.status} />}
                </div>

                {status?.status === "approved" && status.approved_at && (
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 16 }}>
                    Registered on {new Date(status.approved_at).toLocaleDateString()}
                    {status.approved_by_name ? ` by ${status.approved_by_name}` : ""}.
                  </div>
                )}

                {confirmReplace ? (
                  <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: 14 }}>
                    <p style={{ fontSize: 13, color: "var(--on-bg)", marginBottom: 12 }}>
                      This will replace {selected.full_name}&apos;s currently registered face ID. Continue?
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setConfirmReplace(false)}>Cancel</button>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => { setConfirmReplace(false); setShowCapture(true); }}
                      >
                        Continue
                      </button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary" onClick={handleRegisterClick}>
                    <i className="ti ti-camera" />
                    {status?.status === "approved" ? "Update Face ID" : "Register Face ID"}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {showCapture && selected && (
        <HRFaceCaptureModal
          employeeUuid={selected.uuid}
          employeeName={selected.full_name}
          isUpdate={status?.status === "approved"}
          onClose={() => setShowCapture(false)}
          onRegistered={handleRegistered}
        />
      )}
    </>
  );
}
