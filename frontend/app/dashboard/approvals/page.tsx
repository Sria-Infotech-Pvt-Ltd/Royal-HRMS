"use client";

import React, { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { ApprovalModal } from "./ApprovalModal";
import StatusCell from "../leave/_components/StatusCell";
import LeaveRequestDetailModal from "../leave/_components/LeaveRequestDetailModal";
import { useToast } from "@/components/ToastProvider";
import { LeaveRequest } from "../leave/_data";

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

interface CategoryOption { value: string; label: string; }

type Section = "my-requests" | "approvals";
type RequestType = "leave" | "expense";

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
    </select>
  );
}

// ─── Status filter dropdown ───────────────────────────────────────────────────

function StatusFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      suppressHydrationWarning
      style={SELECT_STYLE}
    >
      <option value="all">All Statuses</option>
      <option value="pending">Pending</option>
      <option value="approved">Approved</option>
      <option value="rejected">Rejected</option>
    </select>
  );
}

// ─── New Leave modal ──────────────────────────────────────────────────────────

const LEAVE_TYPES = [
  { value: "casual",    label: "Casual Leave"    },
  { value: "sick",      label: "Sick Leave"      },
  { value: "earned",    label: "Earned Leave"    },
  { value: "lop",       label: "Loss of Pay"     },
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

  async function handleSubmit() {
    if (!form.leave_type || !form.start_date || !form.end_date) {
      setError("Leave type, start date, and end date are required.");
      return;
    }
    if (form.reason.trim().length < 10) {
      setError("Reason must be at least 10 characters.");
      return;
    }
    setSaving(true); setError("");
    try {
      await clientApi.post(API.leave.requests, form);
      onSubmitted(); onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to submit request.", "error");
    } finally { setSaving(false); }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">New Leave Request</div>
          <button className="modal-close" suppressHydrationWarning onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}
          {/* API errors (e.g. duplicate-date validation) now surface as a toast instead. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group">
              <label className="field-label">Leave Type <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className="field-input"
                value={form.leave_type} onChange={e => setForm(f => ({ ...f, leave_type: e.target.value }))}
                style={{ backgroundImage: CHEVRON, backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center", backgroundSize: "15px", paddingRight: "2.5rem", appearance: "none" }}
              >
                <option value="">Select leave type</option>
                {LEAVE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Duration <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className="field-input"
                value={form.duration} onChange={e => setForm(f => ({ ...f, duration: e.target.value }))}
                style={{ backgroundImage: CHEVRON, backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center", backgroundSize: "15px", paddingRight: "2.5rem", appearance: "none" }}
              >
                {DURATIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field-group">
                <label className="field-label">Start Date <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="date" className="field-input" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div className="field-group">
                <label className="field-label">End Date <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="date" className="field-input" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Reason <span style={{ color: "var(--error)" }}>*</span></label>
              <textarea className="field-input" rows={3} placeholder="Briefly describe the reason for your leave request (min. 10 characters)" value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} style={{ resize: "vertical" }} />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" suppressHydrationWarning onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" suppressHydrationWarning onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit Request"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── New Expense modal ────────────────────────────────────────────────────────

function NewExpenseModal({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) {
  const [form, setForm]           = useState({ category: "", amount: "", description: "", expense_date: "" });
  const [catInput, setCatInput]   = useState("");
  const [catOpen, setCatOpen]     = useState(false);
  const [extraCats, setExtraCats] = useState<CategoryOption[]>([]);

  const { data: fetchedCats } = useFetch<CategoryOption[]>(API.expenses.categories);
  const FALLBACK_CATS: CategoryOption[] = [
    { value: "travel",    label: "Travel"    },
    { value: "meals",     label: "Meals"     },
    { value: "equipment", label: "Equipment" },
    { value: "other",     label: "Other"     },
  ];
  const baseCats: CategoryOption[] = (Array.isArray(fetchedCats) && fetchedCats.length > 0)
    ? fetchedCats
    : FALLBACK_CATS;

  const [files, setFiles]     = useState<File[]>([]);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState("");

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name));
      return [...prev, ...selected.filter(f => !names.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setFiles(prev => prev.filter(f => f.name !== name));
  }

  async function handleSubmit() {
    if (!form.category || !form.amount || !form.expense_date) { setError("Category, amount, and date are required."); return; }
    if (files.length === 0) { setError("Please attach at least one receipt."); return; }
    setSaving(true); setError("");
    try {
      const body = new FormData();
      body.append("category",     form.category);
      body.append("amount",       form.amount);
      body.append("expense_date", form.expense_date);
      body.append("description",  form.description);
      files.forEach(f => body.append("receipts", f));
      await clientApi.post(API.expenses.list, body, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onSubmitted(); onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg || "Failed to submit expense.");
    } finally { setSaving(false); }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">New Expense Claim</div>
          <button className="modal-close" suppressHydrationWarning onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group" style={{ position: "relative" }}>
              <label className="field-label">Category <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className="field-input"
                placeholder="Select or type a category"
                value={catInput}
                onChange={e => { setCatInput(e.target.value); setCatOpen(true); setForm(f => ({ ...f, category: e.target.value })); }}
                onFocus={() => setCatOpen(true)}
                onBlur={() => setTimeout(() => setCatOpen(false), 150)}
                autoComplete="off"
              />
              {catOpen && (() => {
                const allCats = [...baseCats, ...extraCats];
                const q = catInput.trim().toLowerCase();
                const filtered = allCats.filter(c => c.label.toLowerCase().includes(q));
                const isNew = catInput.trim() !== "" && !allCats.some(c => c.label.toLowerCase() === q || c.value.toLowerCase() === q);
                if (filtered.length === 0 && !isNew) return null;
                return (
                  <div style={{
                    position: "absolute", top: "calc(100% + 2px)", left: 0, right: 0, zIndex: 60,
                    background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 8,
                    boxShadow: "0 4px 16px rgba(0,0,0,0.10)", overflow: "hidden",
                  }}>
                    {filtered.map(c => (
                      <button key={c.value} type="button" suppressHydrationWarning
                        onMouseDown={() => { setForm(f => ({ ...f, category: c.value })); setCatInput(c.label); setCatOpen(false); }}
                        style={{ display: "block", width: "100%", padding: "8px 14px", textAlign: "left", fontSize: 13, background: form.category === c.value ? "rgba(30,78,140,0.07)" : "none", border: "none", cursor: "pointer", color: "var(--on-bg)", borderBottom: "1px solid var(--outline-v)" }}
                      >
                        {c.label}
                      </button>
                    ))}
                    {isNew && (
                      <button type="button" suppressHydrationWarning
                        onMouseDown={() => {
                          const label = catInput.trim();
                          const value = label.toLowerCase().replace(/\s+/g, "_");
                          const opt: CategoryOption = { value, label };
                          setExtraCats(prev => prev.some(c => c.value === value) ? prev : [...prev, opt]);
                          setForm(f => ({ ...f, category: value }));
                          setCatInput(label);
                          setCatOpen(false);
                        }}
                        style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 14px", fontSize: 13, background: "none", border: "none", cursor: "pointer", color: "var(--primary)" }}
                      >
                        <i className="ti ti-plus" style={{ fontSize: 14 }} />
                        Add &ldquo;{catInput.trim()}&rdquo;
                      </button>
                    )}
                  </div>
                );
              })()}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field-group">
                <label className="field-label">Amount (₹) <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="number" min="1" step="0.01" className="field-input" placeholder="0.00" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} />
              </div>
              <div className="field-group">
                <label className="field-label">Expense Date <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="date" className="field-input" value={form.expense_date} onChange={e => setForm(f => ({ ...f, expense_date: e.target.value }))} />
              </div>
            </div>
            <div className="field-group">
              <label className="field-label">Description</label>
              <textarea className="field-input" rows={2} placeholder="Details about the expense" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} style={{ resize: "vertical" }} />
            </div>
            <div className="field-group">
              <label className="field-label">Receipts <span style={{ color: "var(--error)" }}>*</span></label>
              <label style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 12px", borderRadius: 8,
                border: `1.5px dashed ${files.length > 0 ? "var(--primary)" : "var(--outline-v)"}`,
                background: files.length > 0 ? "rgba(30,78,140,0.04)" : "var(--bg)",
                cursor: "pointer", transition: "all 0.12s",
              }}>
                <i className="ti ti-paperclip" style={{ fontSize: 16, color: files.length > 0 ? "var(--primary)" : "var(--outline)", flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: files.length > 0 ? "var(--primary)" : "var(--on-variant)" }}>
                  {files.length > 0 ? `${files.length} file${files.length > 1 ? "s" : ""} selected` : "Click to attach receipts (PDF, JPG, PNG — max 5 MB each)"}
                </span>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  multiple
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </label>
              {files.length > 0 && (
                <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                  {files.map(f => (
                    <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)" }}>
                      <i className="ti ti-file" style={{ fontSize: 14, flexShrink: 0 }} />
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                      <button type="button" suppressHydrationWarning onClick={() => removeFile(f.name)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--error)", padding: 2 }}>
                        <i className="ti ti-x" style={{ fontSize: 12 }} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" suppressHydrationWarning onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" suppressHydrationWarning onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit Claim"}
          </button>
        </div>
      </div>
    </div>
  );
}



// ─── My Requests section ──────────────────────────────────────────────────────

function MyRequestsSection() {
  const [type, setType]     = useState<RequestType>("leave");
  const [filter, setFilter] = useState("all");
  const [showNew, setShowNew] = useState(false);
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const leaveEndpoint   = filter === "all" ? API.leave.requests   : `${API.leave.requests}?status=${filter}`;
  const expenseEndpoint = filter === "all" ? API.expenses.list     : `${API.expenses.list}?status=${filter}`;

  const { data: leaveRaw,   loading: leaveLoading,   error: leaveError,   refetch: refetchLeave   } = useFetch<LeaveListResponse>(type === "leave"   ? leaveEndpoint   : null);
  const { data: expenseRaw, loading: expenseLoading, error: expenseError, refetch: refetchExpense } = useFetch<ExpenseListResponse>(type === "expense" ? expenseEndpoint : null);

  const leaveItems:   LeaveRequest[]   = leaveRaw?.results   ?? [];
  const expenseItems: ExpenseRequest[] = expenseRaw?.results ?? [];

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <TypeDropdown value={type} onChange={(v: RequestType) => { setType(v); setFilter("all"); }} />
          <StatusFilter value={filter} onChange={setFilter} />
        </div>
        <button
          className="btn btn-primary"
          suppressHydrationWarning
          style={{ fontSize: 13 }}
          onClick={() => setShowNew(true)}
        >
          <i className={`ti ${type === "leave" ? "ti-beach" : "ti-wallet"}`} />
          {type === "leave" ? "New Leave Request" : "New Expense Claim"}
        </button>
      </div>

      {type === "leave" && (
        leaveLoading ? <LoadingRow text="Loading leave requests…" /> :
        leaveError   ? <ErrorRow text={leaveError} /> :
        leaveItems.length === 0 ? <EmptyRow icon="ti-beach" text="No leave requests found" /> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                  <Th>Leave Type</Th><Th>From</Th><Th>To</Th><Th>Days</Th>
                  <Th>Reason</Th><Th>Applied On</Th><Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {leaveItems.map((r: LeaveRequest) => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ borderBottom: "1px solid var(--outline-v)", cursor: "pointer" }}>
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
        />
      )}

      {type === "expense" && (
        expenseLoading ? <LoadingRow text="Loading expense claims…" /> :
        expenseError   ? <ErrorRow text={expenseError} /> :
        expenseItems.length === 0 ? <EmptyRow icon="ti-wallet" text="No expense claims found" /> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                  <Th>Category</Th><Th>Amount</Th><Th>Description</Th>
                  <Th>Submitted On</Th><Th>Status</Th><Th>Remarks</Th>
                </tr>
              </thead>
              <tbody>
                {expenseItems.map((r: ExpenseRequest, idx: number) => (
                  <tr key={r.expense_number ?? r.id ?? idx} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                    <td style={TD}>{r.category}</td>
                    <td style={TD}><span style={{ fontWeight: 600 }}>₹{r.amount?.toLocaleString("en-IN")}</span></td>
                    <td style={{ ...TD, maxWidth: 200 }}>
                      <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.description || "—"}</span>
                    </td>
                    <td style={TD}>{formatDate(r.created_at)}</td>
                    <td style={TD}><StatusBadge status={r.status} /></td>
                    <td style={{ ...TD, maxWidth: 180, color: "var(--on-variant)", fontSize: 12 }}>{r.remarks || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {showNew && type === "leave"   && <NewLeaveModal   onClose={() => setShowNew(false)} onSubmitted={refetchLeave}   />}
      {showNew && type === "expense" && <NewExpenseModal onClose={() => setShowNew(false)} onSubmitted={refetchExpense} />}
    </>
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

  const [modal, setModal] = useState<{
    id:            string;
    action:        "approve" | "reject";
    label:         string;
    kind:          RequestType;
    employeeName:  string;
    employeeEmail: string;
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
          onApprove={() => setModal({ id: detailRequest.id, action: "approve", label: `${detailRequest.employee_name}'s leave`, kind: "leave", employeeName: detailRequest.employee_name ?? "", employeeEmail: "" })}
          onReject={() => setModal({ id: detailRequest.id, action: "reject", label: `${detailRequest.employee_name}'s leave`, kind: "leave", employeeName: detailRequest.employee_name ?? "", employeeEmail: "" })}
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

      {modal && (
        <ApprovalModal
          action={modal.action}
          itemLabel={modal.label}
          employeeName={modal.employeeName}
          employeeEmail={modal.employeeEmail}
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
  const [section, setSection] = useState<Section>("my-requests");

  const sections: { key: Section; label: string; icon: string }[] = [
    { key: "my-requests", label: "My Requests",    icon: "ti-inbox"  },
    { key: "approvals",   label: "Team Approvals", icon: "ti-checks" },
  ];

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
        {section === "my-requests" && <MyRequestsSection />}
        {section === "approvals"   && <TeamApprovalsSection />}
      </div>
    </div>
  );
}
