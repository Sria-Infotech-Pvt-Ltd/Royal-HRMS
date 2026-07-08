"use client";

import React, { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";

// ─── Types ────────────────────────────────────────────────────────────────────

interface LeaveRequest {
  id:            string;
  leave_type:    string;
  from_date:     string;
  to_date:       string;
  days:          number;
  reason:        string;
  status:        string;
  applied_on:    string;
  remarks?:      string;
}

interface ExpenseRequest {
  id:           string;
  category:     string;
  amount:       number;
  description:  string;
  status:       string;
  submitted_on: string;
  remarks?:     string;
}

type Tab = "leave" | "expense";

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase() ?? "";
  const map: Record<string, { bg: string; color: string; label: string }> = {
    pending:  { bg: "rgba(234,179,8,0.12)",   color: "#92400e", label: "Pending"  },
    approved: { bg: "rgba(34,197,94,0.12)",   color: "#15803d", label: "Approved" },
    rejected: { bg: "rgba(239,68,68,0.12)",   color: "#b91c1c", label: "Rejected" },
    cancelled:{ bg: "rgba(100,116,139,0.12)", color: "#475569", label: "Cancelled"},
  };
  const cfg = map[s] ?? { bg: "rgba(100,116,139,0.10)", color: "var(--on-variant)", label: status };
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      backgroundColor: cfg.bg, color: cfg.color,
      textTransform: "capitalize",
    }}>
      {cfg.label}
    </span>
  );
}

// ─── New Leave Request Modal ──────────────────────────────────────────────────

interface LeaveType { value: string; label: string }
const LEAVE_TYPES: LeaveType[] = [
  { value: "casual",    label: "Casual Leave"    },
  { value: "sick",      label: "Sick Leave"      },
  { value: "earned",    label: "Earned Leave"    },
  { value: "lop",       label: "Loss of Pay"     },
  { value: "maternity", label: "Maternity Leave" },
  { value: "paternity", label: "Paternity Leave" },
];

function NewLeaveModal({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) {
  const { showToast } = useToast();
  const [form, setForm] = useState({ leave_type: "", from_date: "", to_date: "", reason: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  function set(key: keyof typeof form, value: string) {
    setForm(f => ({ ...f, [key]: value }));
  }

  async function handleSubmit() {
    if (!form.leave_type || !form.from_date || !form.to_date) {
      setError("Leave type, from date, and to date are required.");
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

  const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
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
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group">
              <label className="field-label">Leave Type <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className="field-input"
                value={form.leave_type}
                onChange={e => set("leave_type", e.target.value)}
                style={{
                  backgroundImage: CHEVRON, backgroundRepeat: "no-repeat",
                  backgroundPosition: "right 10px center", backgroundSize: "15px", paddingRight: "2.5rem",
                  appearance: "none",
                }}
              >
                <option value="">Select leave type</option>
                {LEAVE_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field-group">
                <label className="field-label">From Date <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="date" className="field-input" value={form.from_date} onChange={e => set("from_date", e.target.value)} />
              </div>
              <div className="field-group">
                <label className="field-label">To Date <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="date" className="field-input" value={form.to_date} onChange={e => set("to_date", e.target.value)} />
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Reason</label>
              <textarea
                className="field-input"
                rows={3}
                placeholder="Optional reason for leave"
                value={form.reason}
                onChange={e => set("reason", e.target.value)}
                style={{ resize: "vertical" }}
              />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
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

  const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
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
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group">
              <label className="field-label">Category <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className="field-input"
                value={form.category}
                onChange={e => set("category", e.target.value)}
                style={{
                  backgroundImage: CHEVRON, backgroundRepeat: "no-repeat",
                  backgroundPosition: "right 10px center", backgroundSize: "15px", paddingRight: "2.5rem",
                  appearance: "none",
                }}
              >
                <option value="">Select category</option>
                {EXPENSE_CATEGORIES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Amount (₹) <span style={{ color: "var(--error)" }}>*</span></label>
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
                className="field-input"
                rows={3}
                placeholder="Details about the expense"
                value={form.description}
                onChange={e => set("description", e.target.value)}
                style={{ resize: "vertical" }}
              />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit Claim"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Leave Requests Tab ───────────────────────────────────────────────────────

function LeaveTab() {
  const [showNew, setShowNew] = useState(false);
  const [filter, setFilter]   = useState("all");

  const endpoint = filter === "all"
    ? API.leave.requests
    : `${API.leave.requests}?status=${filter}`;

  const { data: raw, loading, error, refetch } = useFetch<LeaveRequest[]>(endpoint);
  const requests = raw ?? [];

  if (loading) return <LoadingRow text="Loading leave requests…" />;
  if (error)   return <ErrorRow text={error} />;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <StatusFilter value={filter} onChange={setFilter} />
        <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => setShowNew(true)}>
          <i className="ti ti-plus" /> New Leave Request
        </button>
      </div>

      {requests.length === 0 ? (
        <EmptyRow icon="ti-beach" text="No leave requests found" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                <Th>Leave Type</Th>
                <Th>From</Th>
                <Th>To</Th>
                <Th>Days</Th>
                <Th>Reason</Th>
                <Th>Applied On</Th>
                <Th>Status</Th>
                <Th>Remarks</Th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                  <td style={TD}>
                    <LeaveBadge type={r.leave_type} />
                  </td>
                  <td style={TD}>{formatDate(r.from_date)}</td>
                  <td style={TD}>{formatDate(r.to_date)}</td>
                  <td style={TD}>{r.days}d</td>
                  <td style={{ ...TD, maxWidth: 180 }}>
                    <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.reason || "—"}
                    </span>
                  </td>
                  <td style={TD}>{formatDate(r.applied_on)}</td>
                  <td style={TD}><StatusBadge status={r.status} /></td>
                  <td style={{ ...TD, maxWidth: 180, color: "var(--on-variant)", fontSize: 12 }}>
                    {r.remarks || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && <NewLeaveModal onClose={() => setShowNew(false)} onSubmitted={refetch} />}
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

  const { data: raw, loading, error, refetch } = useFetch<ExpenseRequest[]>(endpoint);
  const requests = raw ?? [];

  if (loading) return <LoadingRow text="Loading expense claims…" />;
  if (error)   return <ErrorRow text={error} />;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <StatusFilter value={filter} onChange={setFilter} />
        <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => setShowNew(true)}>
          <i className="ti ti-plus" /> New Expense Claim
        </button>
      </div>

      {requests.length === 0 ? (
        <EmptyRow icon="ti-wallet" text="No expense claims found" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
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
                <tr key={r.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                  <td style={TD}>{r.category}</td>
                  <td style={TD}>
                    <span style={{ fontWeight: 600 }}>₹{r.amount?.toLocaleString("en-IN")}</span>
                  </td>
                  <td style={{ ...TD, maxWidth: 200 }}>
                    <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.description || "—"}
                    </span>
                  </td>
                  <td style={TD}>{formatDate(r.submitted_on)}</td>
                  <td style={TD}><StatusBadge status={r.status} /></td>
                  <td style={{ ...TD, maxWidth: 180, color: "var(--on-variant)", fontSize: 12 }}>
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

// ─── Shared helpers ───────────────────────────────────────────────────────────

const TD: React.CSSProperties = { padding: "12px 12px", verticalAlign: "middle" };

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th style={{ textAlign: "left", padding: "10px 12px", color: "var(--on-variant)", fontWeight: 600, whiteSpace: "nowrap", ...style }}>
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
    <div style={{ display: "flex", gap: 4 }}>
      {options.map(o => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          suppressHydrationWarning
          style={{
            padding: "5px 12px", borderRadius: 20, fontSize: 12, fontWeight: 500,
            border: "1.5px solid",
            borderColor: value === o.value ? "var(--primary)" : "var(--outline-v)",
            background: value === o.value ? "rgba(30,78,140,0.08)" : "none",
            color: value === o.value ? "var(--primary)" : "var(--on-variant)",
            cursor: "pointer", transition: "all 0.12s",
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function LeaveBadge({ type }: { type: string }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      background: "rgba(30,78,140,0.08)", color: "var(--primary)",
      textTransform: "capitalize",
    }}>
      {type?.replace(/_/g, " ") ?? "—"}
    </span>
  );
}

function LoadingRow({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 20px", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
      <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--primary)" }} />
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
    <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--on-variant)" }}>
      <i className={`ti ${icon} text-[40px] block mb-3`} style={{ opacity: 0.3 }} />
      <div style={{ fontSize: 14 }}>{text}</div>
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
    { key: "leave",   label: "Leave Requests", icon: "ti-beach"  },
    { key: "expense", label: "Expense Claims",  icon: "ti-wallet" },
  ];

  return (
    <div>
      <div style={{
        display: "flex", gap: 2,
        borderBottom: "2px solid var(--outline-v)",
        marginBottom: 24,
      }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            suppressHydrationWarning
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "10px 18px", fontSize: 13,
              fontWeight: tab === t.key ? 600 : 400,
              color: tab === t.key ? "var(--primary)" : "var(--on-variant)",
              background: "none", border: "none", cursor: "pointer",
              borderBottom: tab === t.key ? "2px solid var(--primary)" : "2px solid transparent",
              marginBottom: -2, transition: "all 0.12s",
            }}
          >
            <i className={`ti ${t.icon} text-[16px]`} />
            {t.label}
          </button>
        ))}
      </div>

      <div className="settings-card">
        {tab === "leave"   && <LeaveTab />}
        {tab === "expense" && <ExpenseTab />}
      </div>
    </div>
  );
}
