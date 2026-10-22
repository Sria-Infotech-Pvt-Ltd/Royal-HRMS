"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import PayslipDocument, { fmtDate, fmtMonth, type PayslipCompany } from "@/components/payroll/PayslipDocument";

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
  draft:       { label: "Processing",   bg: "var(--bg-high)",          color: "var(--on-variant)"  },
  closed:      { label: "Closed",       bg: "var(--bg-high)",          color: "var(--on-variant)"  },
};

function statusBadge(status: string) {
  const b = STATUS_BADGE[status] ?? { label: status, bg: "var(--bg-high)", color: "var(--on-variant)" };
  return (
    <span
      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
      style={{ background: b.bg, color: b.color }}
    >
      {b.label}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MyPayslipPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [ackMsg, setAckMsg] = useState<string | null>(null);

  const { data: slipPage, loading: slipsLoading, error: slipsError, refetch } =
    useFetch<PagedResponse<ApiPayslip>>(API.payroll.myPayslips);

  const { data: me } = useFetch<ApiMe>(API.employees.me);
  const { data: company } = useFetch<PayslipCompany>(API.settings.company);

  const payslips = slipPage?.results ?? [];
  const slip = payslips.find(p => p.id === selectedId) ?? payslips[0] ?? null;

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

  return (
    <div className="flex flex-col gap-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>My Payslips</h1>
          <p className="text-sm mt-1" style={{ color: "var(--on-variant)" }}>View and download your monthly salary statements</p>
        </div>
        <div className="flex items-center gap-2">
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

      {ackMsg && <div className="alert alert-success">{ackMsg}</div>}

      <div className="payslip-layout flex gap-6 items-start">

        {/* ── Sidebar ── */}
        <div className="payslip-sidebar flex flex-col gap-4 w-56 shrink-0">

          {/* Employee card */}
          <div className="card">
            <div className="p-4 text-center" style={{ background: "linear-gradient(to bottom right, var(--primary), var(--primary-c))" }}>
              <div className="w-14 h-14 rounded-full border-2 text-white font-bold text-xl flex items-center justify-center mx-auto mb-2" style={{ background: "rgba(255,255,255,0.2)", borderColor: "rgba(255,255,255,0.4)" }}>
                {me ? initials(me.full_name) : "—"}
              </div>
              <div className="text-white font-semibold text-sm">{me?.full_name ?? "—"}</div>
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
            <div className="py-1 max-h-80 overflow-y-auto">
              {payslips.map(p => {
                const active = (selectedId === p.id) || (!selectedId && payslips[0]?.id === p.id);
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedId(p.id)}
                    className={`w-full text-left px-4 py-2.5 flex items-center justify-between border-l-2 transition-colors ${
                      active ? "border-[var(--primary)] bg-[rgba(30,78,140,0.08)]" : "border-transparent hover:bg-[var(--bg-low)]"
                    }`}
                  >
                    <div>
                      <div className="text-sm font-semibold" style={{ color: active ? "var(--primary)" : "var(--on-bg)" }}>
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
        </div>

        {/* ── Payslip document (shared with the HR payslip view) ── */}
        {slip && (
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
        )}
      </div>

      <style jsx>{`
        @media (max-width: 768px) {
          .payslip-layout {
            flex-direction: column;
          }
          .payslip-sidebar {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
}
