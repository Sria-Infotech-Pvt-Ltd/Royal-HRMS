"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ApprovalModal } from "./ApprovalModal";
import StatusCell from "../leave/_components/StatusCell";
import LeaveRequestDetailModal from "../leave/_components/LeaveRequestDetailModal";
import { LeaveRequest } from "../leave/_data";
import AttendanceApprovalTab from "./_components/AttendanceApprovalTab";
import CorrectionsTab from "../attendance/_components/CorrectionsTab";
import FaceRegistrationApprovalsTab from "./_components/FaceRegistrationApprovalsTab";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ExpenseReceipt {
  id:  string;
  url: string;
}

interface ExpenseRequest {
  id:              string;
  expense_number:  string;
  title:           string;
  category:        string;
  amount:          string | number;
  expense_date:    string;
  description:     string;
  status:          string;
  employee_name:   string;
  employee_email?: string;
  branch_name:     string;
  receipts:        ExpenseReceipt[];
  created_at:      string;
  remarks?:        string;
}

interface PaginatedResponse<T> {
  results:     T[];
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
}

type LeaveListResponse   = PaginatedResponse<LeaveRequest>;
type ExpenseListResponse = PaginatedResponse<ExpenseRequest>;

type Section = "approvals" | "attendance";
type RequestType = "leave" | "expense" | "attendance_correction" | "face_registration";

// ─── Shared helpers ───────────────────────────────────────────────────────────

const TD: React.CSSProperties = { padding: "12px 12px", verticalAlign: "middle" };

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th style={{ textAlign: "left", padding: "10px 12px", color: "var(--on-variant)", fontWeight: 600, whiteSpace: "nowrap", ...style }}>
      {children}
    </th>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase() ?? "";
  const map: Record<string, { bg: string; color: string; label: string }> = {
    pending:   { bg: "rgba(234,179,8,0.12)",   color: "#92400e", label: "Pending"   },
    approved:  { bg: "rgba(34,197,94,0.12)",   color: "#15803d", label: "Approved"  },
    rejected:  { bg: "rgba(239,68,68,0.12)",   color: "#b91c1c", label: "Rejected"  },
    cancelled: { bg: "rgba(100,116,139,0.12)", color: "#475569", label: "Cancelled" },
  };
  const cfg = map[s] ?? { bg: "rgba(100,116,139,0.10)", color: "var(--on-variant)", label: status };
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      backgroundColor: cfg.bg, color: cfg.color, textTransform: "capitalize",
    }}>
      {cfg.label}
    </span>
  );
}

function LeaveBadge({ type }: { type: string }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      background: "rgba(30,78,140,0.08)", color: "var(--primary)", textTransform: "capitalize",
    }}>
      {type?.replace(/_/g, " ") ?? "—"}
    </span>
  );
}

function LoadingRow({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 20px", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
      <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20, color: "var(--primary)" }} />
      {text}
    </div>
  );
}

function ErrorRow({ text }: { text: string }) {
  return <div className="alert alert-error"><i className="ti ti-alert-circle" /> {text}</div>;
}

function EmptyRow({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--on-variant)" }}>
      <i className={`ti ${icon}`} style={{ fontSize: 40, display: "block", marginBottom: 12, opacity: 0.3 }} />
      <div style={{ fontSize: 14 }}>{text}</div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// ─── Shared dropdown styles ───────────────────────────────────────────────────

const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;

const SELECT_STYLE: React.CSSProperties = {
  padding: "6px 32px 6px 10px", fontSize: 13, borderRadius: 8,
  border: "1.5px solid var(--outline-v)", background: "#fff",
  color: "var(--on-bg)", cursor: "pointer", outline: "none",
  appearance: "none",
  backgroundImage: CHEVRON,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 8px center",
  backgroundSize: "14px",
  minWidth: 130,
};

// ─── Type dropdown (Leave / Expense) ─────────────────────────────────────────

function TypeDropdown({ value, onChange }: { value: RequestType; onChange: (v: RequestType) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as RequestType)}
      suppressHydrationWarning
      style={SELECT_STYLE}
    >
      <option value="leave">Leave</option>
      <option value="expense">Expense</option>
      <option value="attendance_correction">Attendance Correction</option>
      <option value="face_registration">Face Registration</option>
    </select>
  );
}

// ─── Team Approvals section ───────────────────────────────────────────────────

function TeamApprovalsSection() {
  const [type, setType] = useState<RequestType>("leave");
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const { data: leaveRaw,      loading: leaveLoading,   error: leaveError,   refetch: refetchLeave   } = useFetch<LeaveListResponse>(  type === "leave"   ? `${API.approvals.leaveRequests}?scope=team` : null);
  const { data: expenseRaw,    loading: expenseLoading, error: expenseError, refetch: refetchExpense } = useFetch<ExpenseListResponse>( type === "expense" ? API.approvals.expenseList                        : null);
  const leaveItems:   LeaveRequest[]   = leaveRaw?.results   ?? [];
  const expenseItems: ExpenseRequest[] = expenseRaw?.results ?? [];

  useEffect(() => {
    function handleLeaveUpdate() { refetchLeave(); }
    window.addEventListener("leave:updated", handleLeaveUpdate);
    return () => window.removeEventListener("leave:updated", handleLeaveUpdate);
  }, [refetchLeave]);

  const [modal, setModal] = useState<{
    id:            string;
    action:        "approve" | "reject";
    label:         string;
    kind:          RequestType;
    employeeName:  string;
    employeeEmail: string;
    autoVars?:     Record<string, string>;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [apiErr, setApiErr] = useState("");

  async function handleConfirm(
    remarks: string,
    templateName?: string,
    extraContext?: Record<string, string>,
  ) {
    if (!modal) return;
    setSaving(true); setApiErr("");
    try {
      if (modal.kind === "leave") {
        await clientApi.post(API.approvals.approveLeave(modal.id), {
          action:        modal.action,
          remarks,
          template_name: templateName,
          extra_context: extraContext,
        });
        refetchLeave();
      } else {
        await clientApi.put(API.expenses.detail(modal.id), {
          status:        modal.action === "approve" ? "approved" : "rejected",
          remarks,
          template_name: templateName,
          extra_context: extraContext,
        });
        refetchExpense();
      }
      setModal(null);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiErr(msg || "Action failed. Please try again.");
    } finally { setSaving(false); }
  }

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <TypeDropdown value={type} onChange={setType} />
      </div>

      {apiErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {apiErr}</div>}

      {type === "leave" && (
        leaveLoading ? <LoadingRow text="Loading pending leave requests…" /> :
        leaveError   ? <ErrorRow text={leaveError} /> :
        leaveItems.length === 0 ? <EmptyRow icon="ti-checks" text="No pending leave requests for your approval" /> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                  <Th>Employee</Th><Th>Leave Type</Th><Th>From</Th><Th>To</Th>
                  <Th>Days</Th><Th>Reason</Th><Th>Applied On</Th><Th style={{ width: 110 }}>Status</Th>
                </tr>
              </thead>
              <tbody>
                {leaveItems.map((r: LeaveRequest) => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ borderBottom: "1px solid var(--outline-v)", cursor: "pointer" }}>
                    <td style={TD}>
                      <div style={{ fontWeight: 500 }}>{r.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_code}</div>
                    </td>
                    <td style={TD}><LeaveBadge type={r.leave_type} /></td>
                    <td style={TD}>{formatDate(r.start_date)}</td>
                    <td style={TD}>{formatDate(r.end_date)}</td>
                    <td style={TD}>{r.total_days}d</td>
                    <td style={{ ...TD, maxWidth: 180 }}>
                      <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.reason || "—"}</span>
                    </td>
                    <td style={TD}>{formatDate(r.created_at)}</td>
                    <td style={TD}><StatusCell request={r} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
          onApprove={() => setModal({ id: detailRequest.id, action: "approve", label: `${detailRequest.employee_name}'s leave`, kind: "leave", employeeName: detailRequest.employee_name ?? "", employeeEmail: "", autoVars: _leaveAutoVars(detailRequest) })}
          onReject={() => setModal({ id: detailRequest.id, action: "reject", label: `${detailRequest.employee_name}'s leave`, kind: "leave", employeeName: detailRequest.employee_name ?? "", employeeEmail: "", autoVars: _leaveAutoVars(detailRequest) })}
        />
      )}

      {type === "expense" && (
        expenseLoading ? <LoadingRow text="Loading pending expense claims…" /> :
        expenseError   ? <ErrorRow text={expenseError} /> :
        expenseItems.length === 0 ? <EmptyRow icon="ti-checks" text="No pending expense claims for your approval" /> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                  <Th>Employee</Th><Th>Category</Th><Th>Amount</Th>
                  <Th>Description</Th><Th>Submitted On</Th><Th style={{ width: 150 }}>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {expenseItems.map((r: ExpenseRequest) => (
                  <tr key={r.expense_number} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                    <td style={TD}>
                      <div style={{ fontWeight: 500 }}>{r.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.branch_name}</div>
                    </td>
                    <td style={TD}>{r.category}</td>
                    <td style={TD}><span style={{ fontWeight: 600 }}>₹{r.amount?.toLocaleString("en-IN")}</span></td>
                    <td style={{ ...TD, maxWidth: 200 }}>
                      <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.description || "—"}</span>
                    </td>
                    <td style={TD}>{formatDate(r.created_at)}</td>
                    <td style={{ ...TD, textAlign: "right" }}>
                      {r.status === "pending" ? (
                        <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                          <button
                            className="btn btn-primary"
                            suppressHydrationWarning
                            style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => setModal({ id: r.expense_number, action: "approve", label: `${r.employee_name}'s expense`, kind: "expense", employeeName: r.employee_name, employeeEmail: r.employee_email ?? "" })}
                          >
                            <i className="ti ti-check" /> Approve
                          </button>
                          <button
                            className="btn btn-ghost"
                            suppressHydrationWarning
                            style={{ padding: "4px 10px", fontSize: 12, color: "var(--error)" }}
                            onClick={() => setModal({ id: r.expense_number, action: "reject", label: `${r.employee_name}'s expense`, kind: "expense", employeeName: r.employee_name, employeeEmail: r.employee_email ?? "" })}
                          >
                            <i className="ti ti-x" /> Reject
                          </button>
                        </div>
                      ) : (
                        <StatusBadge status={r.status} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {type === "attendance_correction" && <CorrectionsTab />}

      {type === "face_registration" && <FaceRegistrationApprovalsTab />}

      {modal && (
        <ApprovalModal
          action={modal.action}
          itemLabel={modal.label}
          employeeName={modal.employeeName}
          employeeEmail={modal.employeeEmail}
          kind={modal.kind === "leave" || modal.kind === "expense" ? modal.kind : undefined}
          entityId={modal.id}
          autoVars={modal.autoVars}
          onConfirm={handleConfirm}
          onClose={() => setModal(null)}
          saving={saving}
        />
      )}
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const user = useCurrentUser();
  const [section, setSection] = useState<Section>("approvals");
  const canApprove      = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "facial_recognition.approve");
  const hasPayrollView  = usePermission("payroll.view");
  const hasLeaveApprove = usePermission("leave.approve");
  // Managers always get this tab. Payroll admins (payroll.view but not leave.approve) also get it.
  // HR (who have leave.approve) use Leave Management page for attendance sign-off instead.
  const canApproveAttendance =
    user?.can_manage_team === true ||
    user?.is_superuser === true ||
    (hasPayrollView && !hasLeaveApprove);

  const sections: { key: Section; label: string; icon: string }[] = useMemo(() => [
    ...(canApprove           ? [{ key: "approvals"  as Section, label: "Team Approvals",       icon: "ti-checks"       }] : []),
    ...(canApproveAttendance ? [{ key: "attendance" as Section, label: "Attendance Approval",  icon: "ti-calendar-check" }] : []),
  ], [canApprove, canApproveAttendance]);

  useEffect(() => {
    if (sections.length > 0 && !sections.some(s => s.key === section)) {
      setSection(sections[0].key);
    }
  }, [section, sections]);

  return (
    <div>
      <div style={{ display: "flex", gap: 2, borderBottom: "2px solid var(--outline-v)", marginBottom: 24 }}>
        {sections.map(s => (
          <button
            key={s.key}
            suppressHydrationWarning
            onClick={() => setSection(s.key)}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "10px 20px", fontSize: 13,
              fontWeight: section === s.key ? 600 : 400,
              color: section === s.key ? "var(--primary)" : "var(--on-variant)",
              background: "none", border: "none", cursor: "pointer",
              borderBottom: section === s.key ? "2px solid var(--primary)" : "2px solid transparent",
              marginBottom: -2, transition: "all 0.12s",
            }}
          >
            <i className={`ti ${s.icon}`} style={{ fontSize: 16 }} />
            {s.label}
          </button>
        ))}
      </div>

      <div className="settings-card">
        {section === "approvals"   && canApprove           && <TeamApprovalsSection />}
        {section === "attendance"  && canApproveAttendance && <AttendanceApprovalTab />}
      </div>
    </div>
  );
}

function _leaveAutoVars(req: LeaveRequest): Record<string, string> {
  const fmt = (d: string) => {
    if (!d) return "";
    return new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  };
  return {
    LEAVE_TYPE:    req.leave_type_display ?? req.leave_type ?? "",
    START_DATE:    fmt(req.start_date),
    END_DATE:      fmt(req.end_date),
    TOTAL_DAYS:    String(req.total_days ?? ""),
    REASON:        req.reason ?? "",
    EMPLOYEE_CODE: req.employee_code ?? "",
    EMPLOYEE_ID:   req.employee_code ?? "",
  };
}
