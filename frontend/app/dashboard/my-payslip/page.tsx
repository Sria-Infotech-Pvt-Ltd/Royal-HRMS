"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import PayslipDocument, { fmtDate, fmtMonth, type PayslipCompany } from "@/components/payroll/PayslipDocument";
import PayslipPrintCopy from "@/components/payroll/PayslipPrint";
import {
  QUERY_MAX_LENGTH, QUERY_STATUS_LABEL, canRaiseQuery, queriesFor, validateQueryText, type PayslipQueryRow,
} from "@/lib/payslipQuery";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ApiPayslip {
  id: string;
  cycle: string;
  cycle_start: string;
  cycle_end: string;
  pay_date: string;
  employee_name: string;
  employee_id_code: string;
  department: string;
  branch: string;
  annual_ctc: string;
  monthly_ctc: string;
  basic: string;
  hra: string;
  special_allowance: string;
  other_earnings: Record<string, number>;
  other_deductions?: Record<string, number>;
  reimbursements: string;
  bonus: string;
  gross_earnings: string;
  total_working_days: number;
  lop_days: string;
  lop_deduction: string;
  pf_employee: string;
  esi_employee: string;
  pt_deduction: string;
  lwf_employee: string;
  total_deductions: string;
  net_pay: string;
  status: string;
  payslip_pdf: string | null;
  sent_at: string | null;
  query_deadline?: string | null;
  paid_at: string | null;
  open_query_count: number;
}

interface ApiMe {
  full_name: string;
  employee_id: string;
  department: string;
  designation: string;
  date_of_joining: string | null;
  profile?: {
    bank_name?: string;
    account_number?: string;
    ifsc_code?: string;
  };
}

interface PagedResponse<T> { results: T[]; count: number; }

// ── Helpers ───────────────────────────────────────────────────────────────────

function initials(name: string) {
  return name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

const STATUS_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  paid:        { label: "Paid",         bg: "var(--success-c)",        color: "var(--success)"     },
  sent:        { label: "Received",     bg: "rgba(30, 78, 140, 0.12)", color: "var(--primary)"     },
  acknowledged:{ label: "Acknowledged", bg: "rgba(173, 149, 207, 0.15)", color: "var(--purple)"    },
  queried:     { label: "Query open",   bg: "var(--warn-c)",           color: "var(--warn)"        },
  resolved:    { label: "Query resolved", bg: "var(--info-c)",         color: "var(--info)"        },
  draft:       { label: "Processing",   bg: "var(--bg-high)",          color: "var(--on-variant)"  },
  closed:      { label: "Closed",       bg: "var(--bg-high)",          color: "var(--on-variant)"  },
};

function statusBadge(status: string) {
  const b = STATUS_BADGE[status] ?? { label: status, bg: "var(--bg-high)", color: "var(--on-variant)" };
  return (
    <span
      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full whitespace-nowrap"
      style={{ background: b.bg, color: b.color }}
    >
      {b.label}
    </span>
  );
}

const fmtDateTime = (d: string) =>
  new Date(d).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MyPayslipPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [ackMsg, setAckMsg] = useState<string | null>(null);
  const [queryOpen, setQueryOpen] = useState(false);
  const [queryText, setQueryText] = useState("");
  const [queryError, setQueryError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: slipPage, loading: slipsLoading, error: slipsError, refetch } =
    useFetch<PagedResponse<ApiPayslip>>(API.payroll.myPayslips);
  // Always the employee's own queries (?mine=1 also for HR users viewing their own payslips).
  const { data: myQueries, loading: queriesLoading, error: queriesError, refetch: refetchQueries } =
    useFetch<PayslipQueryRow[]>(`${API.payroll.queries}?mine=1`);

  const { data: me } = useFetch<ApiMe>(API.employees.me);
  const { data: company } = useFetch<PayslipCompany>(API.settings.company);

  const payslips = slipPage?.results ?? [];
  const slip = payslips.find(p => p.id === selectedId) ?? payslips[0] ?? null;
  const slipQueries = slip ? queriesFor(myQueries, slip.id) : [];
  const eligibility = slip ? canRaiseQuery(slip) : { allowed: false, reason: null };

  const bankMasked = me?.profile?.account_number
    ? `••••${me.profile.account_number.slice(-4)}`
    : "—";

  async function acknowledge() {
    if (!slip) return;
    setAcknowledging(true);
    try {
      await clientApi.post(API.payroll.acknowledgePayslip(slip.id));
      setAckMsg("Payslip acknowledged.");
      refetch();
      setTimeout(() => setAckMsg(null), 3000);
    } catch {
      setAckMsg("Failed to acknowledge. Please try again.");
    } finally {
      setAcknowledging(false);
    }
  }

  function openQuery() {
    setQueryText("");
    setQueryError(null);
    setQueryOpen(true);
  }

  async function submitQuery() {
    if (!slip || submitting) return;
    const problem = validateQueryText(queryText);
    if (problem) { setQueryError(problem); return; }
    setSubmitting(true);
    setQueryError(null);
    try {
      await clientApi.post(API.payroll.queries, { payslip: slip.id, description: queryText.trim() });
      setQueryOpen(false);
      setAckMsg("Your query has been sent to HR.");
      setTimeout(() => setAckMsg(null), 4000);
      refetch();
      refetchQueries();
    } catch (err) {
      // The server decides eligibility (window, status, ownership) — show its reason.
      setQueryError(apiMessage(err, "Could not raise the query. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  if (slipsLoading) {
    return (
      <div className="empty-state">
        <i className="ti ti-loader-2 animate-spin text-2xl" />
        <div className="empty-state-desc mt-2">Loading your payslips…</div>
      </div>
    );
  }

  if (slipsError) {
    return <div className="alert alert-error">Failed to load payslips. Please refresh.</div>;
  }

  if (payslips.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>My Payslips</h1>
          <p className="text-sm mt-1" style={{ color: "var(--on-variant)" }}>View and download your monthly salary statements</p>
        </div>
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <div className="empty-state-title">No payslips yet</div>
          <div className="empty-state-desc">Your payslips will appear here once payroll is processed for your account.</div>
        </div>
      </div>
    );
  }

  const doc = slip && (
    <PayslipDocument
      slip={slip}
      company={company}
      strip={[
        ["Employee ID",  slip.employee_id_code || "—"],
        ["Bank",        me?.profile?.bank_name || "—"],
        ["Account No.", bankMasked],
        ["IFSC Code",   me?.profile?.ifsc_code || "—"],
      ]}
      netSubline={`Paid on ${fmtDate(slip.pay_date)}${me?.profile?.bank_name ? ` · ${me.profile.bank_name} ${bankMasked}` : ""}`}
    />
  );

  return (
    <div className="payslip-page flex flex-col gap-6">

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>My Payslips</h1>
          <p className="text-sm mt-1" style={{ color: "var(--on-variant)" }}>View and download your monthly salary statements</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {slip?.status === "sent" && (
            <button
              onClick={acknowledge}
              disabled={acknowledging}
              className="btn btn-outline disabled:opacity-50"
            >
              <i className="ti ti-check text-sm" />
              {acknowledging ? "Acknowledging…" : "Acknowledge"}
            </button>
          )}
          {eligibility.allowed && (
            <button onClick={openQuery} className="btn btn-outline">
              <i className="ti ti-message-question text-sm" /> Raise Query
            </button>
          )}
          <button onClick={() => window.print()} className="btn btn-ghost" disabled={!slip}
            title="Print, or choose “Save as PDF” in the print dialog">
            <i className="ti ti-printer text-sm" /> Print / Save PDF
          </button>
          {slip?.payslip_pdf ? (
            <a
              href={slip.payslip_pdf}
              target="_blank"
              rel="noreferrer"
              className="btn btn-filled"
            >
              <i className="ti ti-download text-sm" /> Download PDF
            </a>
          ) : (
            <button
              disabled
              className="btn btn-filled disabled:opacity-50 disabled:cursor-not-allowed"
              title="PDF not yet available for this payslip"
            >
              <i className="ti ti-download text-sm" /> Download PDF
            </button>
          )}
        </div>
      </div>

      {ackMsg && <div className="alert alert-success" style={{ marginBottom: 0 }}>{ackMsg}</div>}

      <div className="payslip-layout">

        {/* ── Sidebar ── */}
        <aside className="payslip-sidebar flex flex-col gap-4">

          {/* Employee card */}
          <div className="card">
            <div className="p-4 text-center" style={{ background: "linear-gradient(to bottom right, var(--primary), var(--primary-c))" }}>
              <div className="w-14 h-14 rounded-full border-2 text-white font-bold text-xl flex items-center justify-center mx-auto mb-2" style={{ background: "rgba(255,255,255,0.2)", borderColor: "rgba(255,255,255,0.4)" }}>
                {me ? initials(me.full_name) : "—"}
              </div>
              <div className="text-white font-semibold text-sm break-words">{me?.full_name ?? "—"}</div>
              <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.75)" }}>{me?.designation ?? "—"}</div>
              <div className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.6)" }}>{me?.employee_id ?? "—"}</div>
            </div>
            <div className="p-3">
              {([
                ["Department", me?.department],
                ["Date of Join", me?.date_of_joining ? fmtDate(me.date_of_joining) : null],
              ] as [string, string | null | undefined][]).map(([k, v]) => (
                <div key={k} className="flex flex-col py-2 border-b border-[var(--outline-v)] last:border-0">
                  <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--outline)" }}>{k}</span>
                  <span className="text-xs font-semibold mt-0.5" style={{ color: "var(--on-bg)" }}>{v || "—"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Month selector */}
          <div className="card">
            <div className="px-4 py-3 border-b border-[var(--outline-v)]">
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--on-variant)" }}>Select Month</span>
            </div>
            <div className="payslip-months py-1" role="listbox" aria-label="Payslip month">
              {payslips.map(p => {
                const active = (selectedId === p.id) || (!selectedId && payslips[0]?.id === p.id);
                return (
                  <button
                    key={p.id}
                    role="option"
                    aria-selected={active}
                    onClick={() => setSelectedId(p.id)}
                    className={`payslip-month text-left px-4 py-2.5 flex items-center justify-between gap-2 border-l-2 transition-colors ${
                      active ? "border-[var(--primary)] bg-[rgba(30,78,140,0.08)]" : "border-transparent hover:bg-[var(--bg-low)]"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-semibold whitespace-nowrap" style={{ color: active ? "var(--primary)" : "var(--on-bg)" }}>
                        {fmtMonth(p.cycle_start)}
                      </div>
                      <div className="text-[10px] mt-0.5" style={{ color: "var(--outline)" }}>{fmtDate(p.pay_date)}</div>
                    </div>
                    {statusBadge(p.status)}
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* ── Payslip document + queries ── */}
        <div className="payslip-main flex flex-col gap-4 min-w-0">
          {doc}

          {slip && (
            <section className="card" style={{ width: "100%", maxWidth: 820, marginInline: "auto" }} aria-labelledby="payslip-queries-title">
              <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 border-b border-[var(--outline-v)]">
                <h2 id="payslip-queries-title" className="text-sm font-semibold" style={{ color: "var(--on-bg)" }}>
                  <i className="ti ti-message-circle" /> Payslip queries
                </h2>
                {eligibility.allowed ? (
                  <button onClick={openQuery} className="btn btn-ghost btn-sm">
                    <i className="ti ti-plus" /> Raise Query
                  </button>
                ) : eligibility.reason && slipQueries.length === 0 ? (
                  <span className="text-xs" style={{ color: "var(--on-variant)" }}>{eligibility.reason}</span>
                ) : null}
              </div>
              <div className="px-5 py-3">
                {queriesLoading ? (
                  <p className="text-sm" style={{ color: "var(--on-variant)" }}><i className="ti ti-loader-2 animate-spin" /> Loading queries…</p>
                ) : queriesError ? (
                  <p className="text-sm" style={{ color: "var(--error)" }}>Couldn&apos;t load your queries. Please refresh.</p>
                ) : slipQueries.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--on-variant)" }}>
                    No queries on this payslip.
                    {eligibility.allowed && slip.query_deadline ? ` You can raise one until ${fmtDateTime(slip.query_deadline)}.` : ""}
                  </p>
                ) : (
                  <ul className="flex flex-col gap-3">
                    {slipQueries.map(q => (
                      <li key={q.id} className="rounded-lg border p-3" style={{ borderColor: "var(--outline-v)" }}>
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                          <span className="text-xs" style={{ color: "var(--on-variant)" }}>Raised {fmtDateTime(q.created_at)}</span>
                          <span className={`badge ${q.status === "resolved" ? "badge-success" : "badge-warn"}`}>{QUERY_STATUS_LABEL[q.status]}</span>
                        </div>
                        <p className="text-sm whitespace-pre-wrap break-words" style={{ color: "var(--on-bg)" }}>{q.description}</p>
                        {q.status === "resolved" && (
                          <div className="mt-2 rounded-md p-2.5" style={{ background: "var(--bg-low)" }}>
                            <div className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--on-variant)" }}>
                              HR response{q.resolved_by_name ? ` · ${q.resolved_by_name}` : ""}{q.resolved_at ? ` · ${fmtDateTime(q.resolved_at)}` : ""}
                            </div>
                            <p className="text-sm whitespace-pre-wrap break-words" style={{ color: "var(--on-bg)" }}>{q.resolution_note || "—"}</p>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          )}
        </div>
      </div>

      {doc && <PayslipPrintCopy>{doc}</PayslipPrintCopy>}

      {queryOpen && slip && (
        <Modal
          title={<><i className="ti ti-message-question" style={{ marginRight: 8 }} />Raise a query — {fmtMonth(slip.cycle_start)}</>}
          onClose={() => setQueryOpen(false)}
          closeDisabled={submitting}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setQueryOpen(false)} disabled={submitting}>Cancel</button>
              <button className="btn btn-filled" onClick={submitQuery} disabled={submitting || !queryText.trim()}>
                {submitting ? <><i className="ti ti-loader-2 animate-spin" /> Sending…</> : <><i className="ti ti-send" /> Send to HR</>}
              </button>
            </>
          }
        >
          <div className="field-group">
            <label className="field-label" htmlFor="payslip-query-text">What looks wrong on this payslip? *</label>
            <textarea
              id="payslip-query-text"
              className="field-input"
              rows={5}
              maxLength={QUERY_MAX_LENGTH}
              value={queryText}
              disabled={submitting}
              placeholder="e.g. HRA is missing this month, or LOP shows 2 days but I was on approved leave."
              onChange={e => { setQueryText(e.target.value); setQueryError(null); }}
            />
            <span className="text-[11px]" style={{ color: "var(--on-variant)" }}>
              {queryText.trim().length}/{QUERY_MAX_LENGTH} · HR will reply here.
              {slip.query_deadline ? ` Queries close ${fmtDateTime(slip.query_deadline)}.` : ""}
            </span>
          </div>
          {queryError && (
            <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}><i className="ti ti-alert-circle" /> {queryError}</div>
          )}
        </Modal>
      )}

      <style jsx>{`
        .payslip-page { width: 100%; max-width: 1180px; margin-inline: auto; }
        .payslip-layout {
          display: grid;
          grid-template-columns: 240px minmax(0, 1fr);
          gap: 24px;
          align-items: start;
        }
        .payslip-months { max-height: 20rem; overflow-y: auto; }
        .payslip-month { width: 100%; }
        @media (max-width: 900px) {
          .payslip-layout { grid-template-columns: minmax(0, 1fr); }
          .payslip-sidebar { display: grid; grid-template-columns: minmax(0, 1fr); }
          /* Months become a horizontal strip above the payslip. */
          .payslip-months { display: flex; overflow-x: auto; overflow-y: hidden; max-height: none; gap: 4px; padding: 6px; }
          .payslip-month { width: auto; flex: 0 0 auto; border-left-width: 0; border-bottom-width: 2px; border-radius: 6px; }
        }
      `}</style>
    </div>
  );
}
