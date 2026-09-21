"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";

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

interface ApiCompany {
  company_name:   string;
  address:        string;
  city:           string;
  state:          string;
  pin_code:       string;
  cin:            string;
  official_phone: string;
  logo_url?:      string | null;
  logo?:          string | null;
}

interface PagedResponse<T> { results: T[]; count: number; }

// ── Helpers ───────────────────────────────────────────────────────────────────

const INR = (n: string | number) =>
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

const fmtDate = (d: string) => formatDate(d);

const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

function initials(name: string) {
  return name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

const STATUS_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  paid:        { label: "Paid",         bg: "var(--success-c)",        color: "var(--success)"     },
  sent:        { label: "Received",     bg: "rgba(124, 58, 237, 0.12)", color: "var(--primary)"     },
  acknowledged:{ label: "Acknowledged", bg: "rgba(167, 139, 250, 0.15)", color: "var(--purple)"    },
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

// ── Row components ─────────────────────────────────────────────────────────────

function EarningRow({ label, value }: { label: string; value: string | number }) {
  const n = Number(value);
  if (n === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-[var(--outline-v)] last:border-0">
      <span className="text-sm" style={{ color: "var(--on-variant)" }}>{label}</span>
      <span className="text-sm font-semibold" style={{ color: "var(--on-bg)" }}>{INR(n)}</span>
    </div>
  );
}

function DeductionRow({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  const n = Number(value);
  if (n === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-[var(--outline-v)] last:border-0">
      <span className="text-sm" style={{ color: "var(--on-variant)" }}>{label}</span>
      <span className="text-sm font-semibold" style={{ color: "var(--error)", opacity: highlight ? 1 : 0.85 }}>{INR(n)}</span>
    </div>
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
  const { data: company } = useFetch<ApiCompany>(API.settings.company);

  const payslips = slipPage?.results ?? [];
  const slip = payslips.find(p => p.id === selectedId) ?? payslips[0] ?? null;

  const gross  = Number(slip?.gross_earnings  ?? 0);
  const ded    = Number(slip?.total_deductions ?? 0);
  const net    = Number(slip?.net_pay         ?? 0);
  const reimb  = Number(slip?.reimbursements  ?? 0);
  const lopAmt = Number(slip?.lop_deduction   ?? 0);
  const lopDays = Number(slip?.lop_days ?? 0);

  const companyAddress = company
    ? [company.address, company.city, company.state, company.pin_code].filter(Boolean).join(", ")
    : "";

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
                      active ? "border-[var(--primary)] bg-[rgba(124,58,237,0.08)]" : "border-transparent hover:bg-[var(--bg-low)]"
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

        {/* ── Payslip document ── */}
        {slip && (
          <div className="payslip-doc card flex-1 min-w-0" style={{ boxShadow: "var(--shadow)" }}>

            {/* Company letterhead */}
            <div className="px-7 py-6" style={{ background: "linear-gradient(to right, var(--primary), var(--primary), var(--primary-c))" }}>
              <div className="flex items-start justify-between">
                <div>
                  {(company?.logo_url || company?.logo) && (
                    <img
                      src={company.logo_url ?? company.logo ?? ""}
                      alt={company.company_name}
                      style={{ maxHeight: 48, maxWidth: 160, objectFit: "contain", marginBottom: 8 }}
                    />
                  )}
                  <div className="text-white font-bold text-lg leading-tight">
                    {company?.company_name ?? "—"}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.75)" }}>{companyAddress}</div>
                  {company?.cin && (
                    <div className="text-[11px] mt-0.5" style={{ color: "rgba(255,255,255,0.6)" }}>CIN: {company.cin}</div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-white font-extrabold text-2xl tracking-wide">PAYSLIP</div>
                  <div className="text-sm mt-1 font-medium" style={{ color: "rgba(255,255,255,0.75)" }}>{fmtMonth(slip.cycle_start)}</div>
                  <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.6)" }}>Salary Date: {fmtDate(slip.pay_date)}</div>
                </div>
              </div>
            </div>

            {/* Employee details strip */}
            <div className="payslip-detail-strip grid grid-cols-4 border-b" style={{ background: "var(--bg-low)", borderColor: "var(--outline-v)" }}>
              {([
                ["Employee ID",  slip.employee_id_code || "—"],
                ["Bank",        me?.profile?.bank_name || "—"],
                ["Account No.", bankMasked],
                ["IFSC Code",   me?.profile?.ifsc_code || "—"],
              ] as [string, string][]).map(([label, value], idx) => (
                <div key={label} className="px-5 py-3 border-[var(--outline-v)]" style={{ borderLeftWidth: idx > 0 ? 1 : 0, borderLeftStyle: "solid" }}>
                  <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: "var(--outline)" }}>{label}</div>
                  <div className="text-xs font-semibold font-mono" style={{ color: "var(--on-bg)" }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Attendance summary */}
            <div className="flex items-center mx-6 mt-5 mb-5 rounded-xl overflow-hidden border" style={{ borderColor: "var(--outline-v)" }}>
              {[
                {
                  label: "Working Days",
                  value: slip.total_working_days,
                  color: "var(--on-bg)",
                  sub: fmtMonth(slip.cycle_start),
                },
                {
                  label: "Paid Days",
                  value: slip.total_working_days - lopDays,
                  color: "var(--success)",
                  sub: "days credited",
                },
                {
                  label: "Loss of Pay",
                  value: lopDays > 0 ? lopDays : 0,
                  color: lopDays > 0 ? "var(--error)" : "var(--outline)",
                  sub: lopDays > 0 ? `${INR(lopAmt)} deducted` : "no LOP",
                },
              ].map((item, i) => (
                <div key={i} className="flex-1 text-center py-3 border-[var(--outline-v)]" style={{ background: "var(--surface)", borderRightWidth: i < 2 ? 1 : 0, borderRightStyle: "solid" }}>
                  <div className="text-2xl font-extrabold" style={{ color: item.color }}>{item.value}</div>
                  <div className="text-[11px] font-medium mt-0.5" style={{ color: "var(--on-variant)" }}>{item.label}</div>
                  <div className="text-[10px]" style={{ color: "var(--outline)" }}>{item.sub}</div>
                </div>
              ))}
            </div>

            {/* Earnings + Deductions */}
            <div className="payslip-earn-ded grid grid-cols-2 gap-0 mx-6 mb-5 rounded-xl overflow-hidden border" style={{ borderColor: "var(--outline-v)" }}>

              {/* Earnings */}
              <div className="border-r" style={{ borderColor: "var(--outline-v)" }}>
                <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ background: "var(--success-c)", borderColor: "var(--success-c)" }}>
                  <div className="w-1 h-4 rounded-full" style={{ background: "var(--success)" }} />
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--success)" }}>Earnings</span>
                </div>
                <div className="px-4 py-2">
                  <EarningRow label="Basic Salary"               value={slip.basic} />
                  <EarningRow label="House Rent Allowance (HRA)" value={slip.hra} />
                  <EarningRow label="Special Allowance"          value={slip.special_allowance} />
                  <EarningRow label="Bonus"                      value={slip.bonus} />
                  {Object.entries(slip.other_earnings ?? {}).map(([name, amt]) => (
                    <EarningRow key={name} label={name} value={amt} />
                  ))}
                </div>
                <div className="flex justify-between items-center px-4 py-3 border-t mt-1" style={{ background: "var(--success-c)", borderColor: "var(--success-c)" }}>
                  <span className="text-sm font-bold" style={{ color: "var(--success)" }}>Gross Earnings</span>
                  <span className="text-base font-extrabold" style={{ color: "var(--success)" }}>{INR(gross)}</span>
                </div>
              </div>

              {/* Deductions */}
              <div>
                <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ background: "var(--error-c)", borderColor: "var(--error-c)" }}>
                  <div className="w-1 h-4 rounded-full" style={{ background: "var(--error)" }} />
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--error)" }}>Deductions</span>
                </div>
                <div className="px-4 py-2">
                  <DeductionRow label="Provident Fund (PF)"  value={slip.pf_employee} />
                  <DeductionRow label="ESI"                   value={slip.esi_employee} />
                  <DeductionRow label="Professional Tax (PT)" value={slip.pt_deduction} />
                  <DeductionRow label="Labour Welfare Fund"   value={slip.lwf_employee} />
                  <DeductionRow label="Loss of Pay (LOP)"     value={slip.lop_deduction} highlight />
                </div>
                <div className="flex justify-between items-center px-4 py-3 border-t mt-1" style={{ background: "var(--error-c)", borderColor: "var(--error-c)" }}>
                  <span className="text-sm font-bold" style={{ color: "var(--error)" }}>Total Deductions</span>
                  <span className="text-base font-extrabold" style={{ color: "var(--error)" }}>{INR(ded)}</span>
                </div>
              </div>
            </div>

            {/* Reimbursements — shown only if non-zero */}
            {reimb > 0 && (
              <div className="mx-6 mb-5 rounded-xl border overflow-hidden" style={{ borderColor: "var(--info-c)", background: "var(--info-c)" }}>
                <div className="flex items-center gap-2 px-4 py-3">
                  <i className="ti ti-receipt text-sm" style={{ color: "var(--info)" }} />
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--info)" }}>Reimbursements</span>
                  <span className="ml-auto text-sm font-bold" style={{ color: "var(--info)" }}>{INR(reimb)}</span>
                </div>
              </div>
            )}

            {/* Net salary banner */}
            <div className="mx-6 mb-6 rounded-xl overflow-hidden" style={{ background: "var(--success)" }}>
              <div className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="text-sm font-medium" style={{ color: "rgba(255,255,255,0.85)" }}>Net Salary Credited</div>
                  <div className="text-white text-xs mt-1 opacity-80">
                    Paid on {fmtDate(slip.pay_date)}
                    {me?.profile?.bank_name ? ` · ${me.profile.bank_name} ${bankMasked}` : ""}
                  </div>
                  <div className="flex items-center gap-3 mt-3 text-xs" style={{ color: "rgba(255,255,255,0.75)" }}>
                    <span>Gross {INR(gross)}</span>
                    <span style={{ color: "rgba(255,255,255,0.5)" }}>−</span>
                    <span>Ded. {INR(ded)}</span>
                    {reimb > 0 && (
                      <>
                        <span style={{ color: "rgba(255,255,255,0.5)" }}>+</span>
                        <span>Reimb. {INR(reimb)}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-extrabold text-white tracking-tight">{INR(net)}</div>
                  <div className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.75)" }}>In Hand</div>
                </div>
              </div>
              <div className="h-1.5 flex">
                <div style={{ background: "rgba(255,255,255,0.3)", width: `${gross + ded > 0 ? Math.round((gross / (gross + ded)) * 100) : 50}%` }} />
                <div className="flex-1" style={{ background: "var(--error)", opacity: 0.6 }} />
              </div>
            </div>

            {/* Footer */}
            <div className="text-center text-[11px] pb-5" style={{ color: "var(--outline)" }}>
              This is a computer-generated payslip and does not require a signature.
              {company?.official_phone && (
                <> For queries contact HR at <span style={{ color: "var(--primary)" }}>{company.official_phone}</span>.</>
              )}
            </div>
          </div>
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
        @media (max-width: 560px) {
          .payslip-detail-strip {
            grid-template-columns: 1fr 1fr;
          }
          .payslip-earn-ded {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
