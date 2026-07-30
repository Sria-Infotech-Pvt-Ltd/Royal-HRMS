"use client";

import React, { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { LeaveRequest, PaginatedResponse, fmtDate } from "../leave/_data";
import LeaveRequestDetailModal from "../leave/_components/LeaveRequestDetailModal";
import StatusCell from "../leave/_components/StatusCell";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ExpenseRequest {
  id:           string;
  category:     string;
  amount:       number;
  description:  string;
  status:       string;
  submitted_on: string;
  remarks?:     string;
}

type Tab = "leave" | "expense" | "correction";

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_BADGE_CLASS: Record<string, string> = {
  pending:   "badge badge-warn",
  approved:  "badge badge-success",
  rejected:  "badge badge-error",
  cancelled: "badge badge-neutral",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending", approved: "Approved", rejected: "Rejected", cancelled: "Cancelled",
};

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase() ?? "";
  return (
    <span className={STATUS_BADGE_CLASS[s] ?? "badge badge-neutral"}>
      {STATUS_LABEL[s] ?? status}
    </span>
  );
}

// ─── New Leave Request Modal ──────────────────────────────────────────────────

interface LeaveType { value: string; label: string }
const LEAVE_TYPES: LeaveType[] = [
  { value: "casual",    label: "Casual Leave"    },
  { value: "sick",      label: "Sick Leave"      },
  { value: "earned",    label: "Earned Leave"    },
  { value: "lwp",       label: "Loss of Pay"     },
  { value: "maternity", label: "Maternity Leave" },
  { value: "paternity", label: "Paternity Leave" },
];

const DURATIONS = [
  { value: "full_day",       label: "Full Day"             },
  { value: "half_morning",   label: "Half Day · Morning"   },
  { value: "half_afternoon", label: "Half Day · Afternoon" },
];

function NewLeaveModal({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) {
  const { showToast } = useToast();
  const [form, setForm] = useState({ leave_type: "", duration: "full_day", start_date: "", end_date: "", reason: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  function set(key: keyof typeof form, value: string) {
    setForm(f => ({ ...f, [key]: value }));
  }

  async function handleSubmit() {
    if (!form.leave_type || !form.start_date || !form.end_date) {
      setError("Leave type, start date, and end date are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await clientApi.post(API.leave.requests, form);
      onSubmitted();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to submit request.", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal max-w-[480px]">
        <div className="modal-header">
          <div className="modal-title">New Leave Request</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {error}
            </div>
          )}
          <div className="flex flex-col gap-3.5">
            <div className="field-group">
              <label className="field-label">Leave Type <span className="text-[var(--error)]">*</span></label>
              <select
                className="field-input field-select"
                value={form.leave_type}
                onChange={e => set("leave_type", e.target.value)}
              >
                <option value="">Select leave type</option>
                {LEAVE_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Duration <span className="text-[var(--error)]">*</span></label>
              <select
                className="field-input field-select"
                value={form.duration}
                onChange={e => set("duration", e.target.value)}
              >
                {DURATIONS.map(d => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="field-group">
                <label className="field-label">Start Date <span className="text-[var(--error)]">*</span></label>
                <input type="date" className="field-input" value={form.start_date} onChange={e => set("start_date", e.target.value)} />
              </div>
              <div className="field-group">
                <label className="field-label">End Date <span className="text-[var(--error)]">*</span></label>
                <input type="date" className="field-input" value={form.end_date} onChange={e => set("end_date", e.target.value)} />
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Reason</label>
              <textarea
                className="field-input resize-y"
                rows={3}
                placeholder="Optional reason for leave"
                value={form.reason}
                onChange={e => set("reason", e.target.value)}
              />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit Request"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── New Expense Modal ────────────────────────────────────────────────────────

const EXPENSE_CATEGORIES = [
  "Travel", "Accommodation", "Food", "Office Supplies",
  "Client Entertainment", "Communication", "Training", "Medical", "Other",
];

function NewExpenseModal({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) {
  const [form, setForm] = useState({ category: "", amount: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  function set(key: keyof typeof form, value: string) {
    setForm(f => ({ ...f, [key]: value }));
  }

  async function handleSubmit() {
    if (!form.category || !form.amount) {
      setError("Category and amount are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await clientApi.post(API.expenses.list, {
        category:    form.category,
        amount:      parseFloat(form.amount),
        description: form.description,
      });
      onSubmitted();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg || "Failed to submit expense.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal max-w-[480px]">
        <div className="modal-header">
          <div className="modal-title">New Expense Claim</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {error}
            </div>
          )}
          <div className="flex flex-col gap-3.5">
            <div className="field-group">
              <label className="field-label">Category <span className="text-[var(--error)]">*</span></label>
              <select
                className="field-input field-select"
                value={form.category}
                onChange={e => set("category", e.target.value)}
              >
                <option value="">Select category</option>
                {EXPENSE_CATEGORIES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Amount (₹) <span className="text-[var(--error)]">*</span></label>
              <input
                type="number"
                min="1"
                step="0.01"
                className="field-input"
                placeholder="0.00"
                value={form.amount}
                onChange={e => set("amount", e.target.value)}
              />
            </div>
            <div className="field-group">
              <label className="field-label">Description</label>
              <textarea
                className="field-input resize-y"
                rows={3}
                placeholder="Details about the expense"
                value={form.description}
                onChange={e => set("description", e.target.value)}
              />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit Claim"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Leave Requests Tab ───────────────────────────────────────────────────────

function LeaveTab() {
  const { showToast } = useToast();
  const [showNew, setShowNew] = useState(false);
  const [filter, setFilter]   = useState("all");
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const endpoint = filter === "all"
    ? API.leave.requests
    : `${API.leave.requests}?status=${filter}`;

  const { data: raw, loading, error, refetch } = useFetch<PaginatedResponse<LeaveRequest>>(endpoint);
  const requests = raw?.results ?? [];

  async function cancelRequest(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    }
  }

  if (loading) return <LoadingRow text="Loading leave requests…" />;
  if (error)   return <ErrorRow text={error} />;

  return (
    <>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2.5">
        <StatusFilter value={filter} onChange={setFilter} />
        <button className="btn btn-filled" onClick={() => setShowNew(true)}>
          <i className="ti ti-plus" /> New Leave Request
        </button>
      </div>

      {requests.length === 0 ? (
        <EmptyRow icon="ti-beach" text="No leave requests found" />
      ) : (
        <div className="table-wrap">
          <table className="text-[13px]">
            <thead>
              <tr className="border-b-2 border-[var(--outline-v)]">
                <Th>Leave Type</Th>
                <Th>From</Th>
                <Th>To</Th>
                <Th>Days</Th>
                <Th>Reason</Th>
                <Th>Applied On</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id} onClick={() => setDetailRequest(r)} className="cursor-pointer">
                  <td>
                    <LeaveBadge label={r.leave_type_display} />
                  </td>
                  <td>{fmtDate(r.start_date)}</td>
                  <td>{fmtDate(r.end_date)}</td>
                  <td>{r.total_days}d</td>
                  <td className="max-w-[180px]">
                    <span className="block truncate">
                      {r.reason || "—"}
                    </span>
                  </td>
                  <td>{fmtDate(r.created_at)}</td>
                  <td><StatusCell request={r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && <NewLeaveModal onClose={() => setShowNew(false)} onSubmitted={refetch} />}

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
          onCancelRequest={() => cancelRequest(detailRequest.id)}
        />
      )}
    </>
  );
}

// ─── Expense Requests Tab ─────────────────────────────────────────────────────

function ExpenseTab() {
  const [showNew, setShowNew] = useState(false);
  const [filter, setFilter]   = useState("all");

  const endpoint = filter === "all"
    ? API.expenses.list
    : `${API.expenses.list}?status=${filter}`;

  const { data: raw, loading, error, refetch } = useFetch<PaginatedResponse<ExpenseRequest>>(endpoint);
  const requests = raw?.results ?? [];

  if (loading) return <LoadingRow text="Loading expense claims…" />;
  if (error)   return <ErrorRow text={error} />;

  return (
    <>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2.5">
        <StatusFilter value={filter} onChange={setFilter} />
        <button className="btn btn-filled" onClick={() => setShowNew(true)}>
          <i className="ti ti-plus" /> New Expense Claim
        </button>
      </div>

      {requests.length === 0 ? (
        <EmptyRow icon="ti-wallet" text="No expense claims found" />
      ) : (
        <div className="table-wrap">
          <table className="text-[13px]">
            <thead>
              <tr className="border-b-2 border-[var(--outline-v)]">
                <Th>Category</Th>
                <Th>Amount</Th>
                <Th>Description</Th>
                <Th>Submitted On</Th>
                <Th>Status</Th>
                <Th>Remarks</Th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id}>
                  <td>{r.category}</td>
                  <td>
                    <span className="font-semibold">₹{r.amount?.toLocaleString("en-IN")}</span>
                  </td>
                  <td className="max-w-[200px]">
                    <span className="block truncate">
                      {r.description || "—"}
                    </span>
                  </td>
                  <td>{formatDate(r.submitted_on)}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="max-w-[180px] text-[var(--on-variant)] text-xs">
                    {r.remarks || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && <NewExpenseModal onClose={() => setShowNew(false)} onSubmitted={refetch} />}
    </>
  );
}

// ─── Correction Requests Tab ─────────────────────────────────────────────────

interface CorrectionRequest {
  id:               string;
  date:             string;
  punch_type:       "IN" | "OUT" | "BOTH";
  original_in:      string | null;
  original_out:     string | null;
  requested_in:     string | null;
  requested_out:    string | null;
  reason:           string;
  notes:            string;
  status:           string;
  l1_approver_name: string | null;
  l1_status:        string | null;
  l1_remarks:       string;
  l2_approver_name: string | null;
  l2_status:        string | null;
  l2_remarks:       string;
  reviewed_by:      string | null;
  reviewed_at:      string | null;
  created_at:       string;
}

const REASON_LABEL: Record<string, string> = {
  biometric_error:  "Biometric Error",
  forgot_to_punch:  "Forgot to Punch",
  field_work:       "Field Work",
  system_downtime:  "System Downtime",
  other:            "Other",
};

const CORRECTION_STATUS_CLASS: Record<string, string> = {
  pending:    "badge badge-warn",
  l2_pending: "badge badge-info",
  approved:   "badge badge-success",
  rejected:   "badge badge-error",
};

const CORRECTION_STATUS_LABEL: Record<string, string> = {
  pending:    "Pending",
  l2_pending: "L2 Pending",
  approved:   "Approved",
  rejected:   "Rejected",
};

const PUNCH_TYPE_CLASS: Record<string, string> = {
  IN:   "badge badge-success",
  OUT:  "badge badge-primary",
  BOTH: "badge badge-info",
};

function CorrectionTab() {
  const [filter, setFilter] = useState("all");

  const endpoint = filter === "all"
    ? API.attendance.myCorrections
    : `${API.attendance.myCorrections}?status=${filter}`;

  const { data: raw, loading, error } = useFetch<PaginatedResponse<CorrectionRequest>>(endpoint);
  const requests = raw?.results ?? [];

  if (loading) return <LoadingRow text="Loading correction requests…" />;
  if (error)   return <ErrorRow text={error} />;

  return (
    <>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2.5">
        <div className="flex gap-1">
          {[
            { value: "all",        label: "All"        },
            { value: "pending",    label: "Pending"    },
            { value: "l2_pending", label: "L2 Pending" },
            { value: "approved",   label: "Approved"   },
            { value: "rejected",   label: "Rejected"   },
          ].map(o => (
            <button
              key={o.value}
              onClick={() => setFilter(o.value)}
              suppressHydrationWarning
              className={`px-3 py-[5px] rounded-full text-xs font-medium border-[1.5px] cursor-pointer transition-all duration-150 ${
                filter === o.value
                  ? "border-[var(--primary)] bg-[rgba(30,78,140,0.08)] text-[var(--primary)]"
                  : "border-[var(--outline-v)] bg-transparent text-[var(--on-variant)]"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {requests.length === 0 ? (
        <EmptyRow icon="ti-clock-edit" text="No correction requests found" />
      ) : (
        <div className="table-wrap">
          <table className="text-[13px]">
            <thead>
              <tr className="border-b-2 border-[var(--outline-v)]">
                <Th>Date</Th>
                <Th>Type</Th>
                <Th>Original</Th>
                <Th>Requested</Th>
                <Th>Reason</Th>
                <Th>Approvers</Th>
                <Th>Submitted On</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => {
                const remarks = r.l2_remarks || r.l1_remarks || "";
                return (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap font-medium">{formatDate(r.date)}</td>
                    <td>
                      <span className={PUNCH_TYPE_CLASS[r.punch_type] ?? "badge badge-neutral"}>
                        {r.punch_type}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-[var(--on-variant)] whitespace-nowrap">
                      {r.original_in ?? "—"} / {r.original_out ?? "—"}
                    </td>
                    <td className="font-mono text-xs whitespace-nowrap">
                      {r.requested_in ?? "—"} / {r.requested_out ?? "—"}
                    </td>
                    <td className="whitespace-nowrap">{REASON_LABEL[r.reason] ?? r.reason}</td>
                    <td>
                      <div className="flex flex-col gap-0.5 text-xs text-[var(--on-variant)]">
                        {r.l1_approver_name && (
                          <span>L1: {r.l1_approver_name}{r.l1_status ? ` · ${r.l1_status}` : ""}</span>
                        )}
                        {r.l2_approver_name && (
                          <span>L2: {r.l2_approver_name}{r.l2_status ? ` · ${r.l2_status}` : ""}</span>
                        )}
                        {!r.l1_approver_name && !r.l2_approver_name && <span>—</span>}
                        {remarks && (
                          <span className="text-[var(--error)] truncate max-w-[160px]" title={remarks}>
                            {remarks}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap">{r.created_at}</td>
                    <td>
                      <span className={CORRECTION_STATUS_CLASS[r.status] ?? "badge badge-neutral"}>
                        {CORRECTION_STATUS_LABEL[r.status] ?? r.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="whitespace-nowrap">
      {children}
    </th>
  );
}

function StatusFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const options = [
    { value: "all",      label: "All"      },
    { value: "pending",  label: "Pending"  },
    { value: "approved", label: "Approved" },
    { value: "rejected", label: "Rejected" },
  ];
  return (
    <div className="flex gap-1">
      {options.map(o => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          suppressHydrationWarning
          className={`px-3 py-[5px] rounded-full text-xs font-medium border-[1.5px] cursor-pointer transition-all duration-150 ${
            value === o.value
              ? "border-[var(--primary)] bg-[rgba(30,78,140,0.08)] text-[var(--primary)]"
              : "border-[var(--outline-v)] bg-transparent text-[var(--on-variant)]"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function LeaveBadge({ label }: { label: string }) {
  return (
    <span className="badge badge-primary font-semibold">
      {label || "—"}
    </span>
  );
}

function LoadingRow({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center py-[60px] px-5 gap-2 text-[13px] text-[var(--on-variant)]">
      <i className="ti ti-loader-2 animate-spin text-[20px] text-[var(--primary)]" />
      {text}
    </div>
  );
}

function ErrorRow({ text }: { text: string }) {
  return (
    <div className="alert alert-error">
      <i className="ti ti-alert-circle" /> {text}
    </div>
  );
}

function EmptyRow({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="py-[60px] px-5 text-center text-[var(--on-variant)]">
      <i className={`ti ${icon} text-[40px] block mb-3 opacity-30`} />
      <div className="text-sm">{text}</div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MyRequestsPage() {
  const [tab, setTab] = useState<Tab>("leave");

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "leave",      label: "Leave Requests",        icon: "ti-beach"      },
    { key: "expense",    label: "Expense Claims",         icon: "ti-wallet"     },
    { key: "correction", label: "Attendance Corrections", icon: "ti-clock-edit" },
  ];

  return (
    <div>
      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            suppressHydrationWarning
            className={`tab flex items-center gap-[7px] ${tab === t.key ? "active" : ""}`}
          >
            <i className={`ti ${t.icon} text-[16px]`} />
            {t.label}
          </button>
        ))}
      </div>

      <div className="settings-card">
        {tab === "leave"      && <LeaveTab />}
        {tab === "expense"    && <ExpenseTab />}
        {tab === "correction" && <CorrectionTab />}
      </div>
    </div>
  );
}
