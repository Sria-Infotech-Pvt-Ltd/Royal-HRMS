"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

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
  company_name: string;
  address: string;
  city: string;
  state: string;
  pin_code: string;
  cin: string;
  official_phone: string;
}

interface PagedResponse<T> { results: T[]; count: number; }

// ── Helpers ───────────────────────────────────────────────────────────────────

const INR = (n: string | number) =>
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

function initials(name: string) {
  return name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  paid:        { label: "Paid",        cls: "bg-emerald-100 text-emerald-700" },
  sent:        { label: "Received",    cls: "bg-blue-100 text-blue-700"       },
  acknowledged:{ label: "Acknowledged",cls: "bg-violet-100 text-violet-700"  },
  draft:       { label: "Processing",  cls: "bg-gray-100 text-gray-500"      },
  closed:      { label: "Closed",      cls: "bg-gray-100 text-gray-500"      },
};

function statusBadge(status: string) {
  const b = STATUS_BADGE[status] ?? { label: status, cls: "bg-gray-100 text-gray-500" };
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${b.cls}`}>
      {b.label}
    </span>
  );
}

// ── Row components ─────────────────────────────────────────────────────────────

function EarningRow({ label, value }: { label: string; value: string | number }) {
  const n = Number(value);
  if (n === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-semibold text-gray-800">{INR(n)}</span>
    </div>
  );
}

function DeductionRow({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  const n = Number(value);
  if (n === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-sm font-semibold ${highlight ? "text-red-600" : "text-red-500"}`}>{INR(n)}</span>
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
        <i className="ti ti-loader-2 animate-spin text-2xl text-gray-400" />
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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">My Payslips</h1>
          <p className="text-sm text-gray-500 mt-1">View and download your monthly salary statements</p>
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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">My Payslips</h1>
          <p className="text-sm text-gray-500 mt-1">View and download your monthly salary statements</p>
        </div>
        <div className="flex items-center gap-2">
          {slip?.status === "sent" && (
            <button
              onClick={acknowledge}
              disabled={acknowledging}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
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
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors"
            >
              <i className="ti ti-download text-sm" /> Download PDF
            </a>
          ) : (
            <button disabled className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg opacity-50 cursor-not-allowed">
              <i className="ti ti-download text-sm" /> Download PDF
            </button>
          )}
        </div>
      </div>

      {ackMsg && <div className="alert alert-success">{ackMsg}</div>}

      <div className="flex gap-6 items-start">

        {/* ── Sidebar ── */}
        <div className="flex flex-col gap-4 w-56 shrink-0">

          {/* Employee card */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-br from-blue-900 to-blue-700 p-4 text-center">
              <div className="w-14 h-14 rounded-full bg-white/20 border-2 border-white/40 text-white font-bold text-xl flex items-center justify-center mx-auto mb-2">
                {me ? initials(me.full_name) : "—"}
              </div>
              <div className="text-white font-semibold text-sm">{me?.full_name ?? "—"}</div>
              <div className="text-blue-200 text-xs mt-0.5">{me?.designation ?? "—"}</div>
              <div className="text-blue-300 text-[11px] mt-0.5">{me?.employee_id ?? "—"}</div>
            </div>
            <div className="p-3 divide-y divide-gray-100">
              {([
                ["Department", me?.department],
                ["Date of Join", me?.date_of_joining ? fmtDate(me.date_of_joining) : null],
              ] as [string, string | null | undefined][]).map(([k, v]) => (
                <div key={k} className="flex flex-col py-2">
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider">{k}</span>
                  <span className="text-xs font-semibold text-gray-800 mt-0.5">{v || "—"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Month selector */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Select Month</span>
            </div>
            <div className="py-1 max-h-80 overflow-y-auto">
              {payslips.map(p => {
                const active = (selectedId === p.id) || (!selectedId && payslips[0]?.id === p.id);
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedId(p.id)}
                    className={`w-full text-left px-4 py-2.5 flex items-center justify-between border-l-2 transition-colors ${
                      active ? "border-blue-800 bg-blue-50" : "border-transparent hover:bg-gray-50"
                    }`}
                  >
                    <div>
                      <div className={`text-sm font-semibold ${active ? "text-blue-800" : "text-gray-700"}`}>
                        {fmtMonth(p.cycle_start)}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">{fmtDate(p.pay_date)}</div>
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
          <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">

            {/* Company letterhead */}
            <div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-700 px-7 py-6">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-white font-bold text-lg leading-tight">
                    {company?.company_name ?? "—"}
                  </div>
                  <div className="text-blue-200 text-xs mt-1">{companyAddress}</div>
                  {company?.cin && (
                    <div className="text-blue-300 text-[11px] mt-0.5">CIN: {company.cin}</div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-white font-extrabold text-2xl tracking-wide">PAYSLIP</div>
                  <div className="text-blue-200 text-sm mt-1 font-medium">{fmtMonth(slip.cycle_start)}</div>
                  <div className="text-blue-300 text-xs mt-0.5">Salary Date: {fmtDate(slip.pay_date)}</div>
                </div>
              </div>
            </div>

            {/* Employee details strip */}
            <div className="grid grid-cols-4 divide-x divide-gray-100 bg-gray-50 border-b border-gray-200">
              {([
                ["Employee ID",  slip.employee_id_code || "—"],
                ["Bank",        me?.profile?.bank_name || "—"],
                ["Account No.", bankMasked],
                ["IFSC Code",   me?.profile?.ifsc_code || "—"],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} className="px-5 py-3">
                  <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{label}</div>
                  <div className="text-xs font-semibold text-gray-800 font-mono">{value}</div>
                </div>
              ))}
            </div>

            {/* Attendance summary */}
            <div className="flex items-center mx-6 mt-5 mb-5 rounded-xl overflow-hidden border border-gray-200">
              {[
                {
                  label: "Working Days",
                  value: slip.total_working_days,
                  color: "text-gray-900",
                  sub: fmtMonth(slip.cycle_start),
                },
                {
                  label: "Paid Days",
                  value: slip.total_working_days - lopDays,
                  color: "text-emerald-700",
                  sub: "days credited",
                },
                {
                  label: "Loss of Pay",
                  value: lopDays > 0 ? lopDays : 0,
                  color: lopDays > 0 ? "text-red-600" : "text-gray-400",
                  sub: lopDays > 0 ? `${INR(lopAmt)} deducted` : "no LOP",
                },
              ].map((item, i) => (
                <div key={i} className={`flex-1 text-center py-3 bg-white ${i < 2 ? "border-r border-gray-200" : ""}`}>
                  <div className={`text-2xl font-extrabold ${item.color}`}>{item.value}</div>
                  <div className="text-[11px] font-medium text-gray-600 mt-0.5">{item.label}</div>
                  <div className="text-[10px] text-gray-400">{item.sub}</div>
                </div>
              ))}
            </div>

            {/* Earnings + Deductions */}
            <div className="grid grid-cols-2 gap-0 mx-6 mb-5 rounded-xl overflow-hidden border border-gray-200">

              {/* Earnings */}
              <div className="border-r border-gray-200">
                <div className="flex items-center gap-2 px-4 py-3 bg-emerald-50 border-b border-emerald-100">
                  <div className="w-1 h-4 rounded-full bg-emerald-600" />
                  <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider">Earnings</span>
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
                <div className="flex justify-between items-center px-4 py-3 bg-emerald-50 border-t border-emerald-100 mt-1">
                  <span className="text-sm font-bold text-emerald-900">Gross Earnings</span>
                  <span className="text-base font-extrabold text-emerald-700">{INR(gross)}</span>
                </div>
              </div>

              {/* Deductions */}
              <div>
                <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border-b border-red-100">
                  <div className="w-1 h-4 rounded-full bg-red-500" />
                  <span className="text-xs font-bold text-red-800 uppercase tracking-wider">Deductions</span>
                </div>
                <div className="px-4 py-2">
                  <DeductionRow label="Provident Fund (PF)"  value={slip.pf_employee} />
                  <DeductionRow label="ESI"                   value={slip.esi_employee} />
                  <DeductionRow label="Professional Tax (PT)" value={slip.pt_deduction} />
                  <DeductionRow label="Labour Welfare Fund"   value={slip.lwf_employee} />
                  <DeductionRow label="Loss of Pay (LOP)"     value={slip.lop_deduction} highlight />
                </div>
                <div className="flex justify-between items-center px-4 py-3 bg-red-50 border-t border-red-100 mt-1">
                  <span className="text-sm font-bold text-red-900">Total Deductions</span>
                  <span className="text-base font-extrabold text-red-600">{INR(ded)}</span>
                </div>
              </div>
            </div>

            {/* Reimbursements — shown only if non-zero */}
            {reimb > 0 && (
              <div className="mx-6 mb-5 rounded-xl border border-blue-100 bg-blue-50 overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3">
                  <i className="ti ti-receipt text-blue-700 text-sm" />
                  <span className="text-xs font-bold text-blue-800 uppercase tracking-wider">Reimbursements</span>
                  <span className="ml-auto text-sm font-bold text-blue-700">{INR(reimb)}</span>
                </div>
              </div>
            )}

            {/* Net salary banner */}
            <div className="mx-6 mb-6 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="text-emerald-100 text-sm font-medium">Net Salary Credited</div>
                  <div className="text-white text-xs mt-1 opacity-80">
                    Paid on {fmtDate(slip.pay_date)}
                    {me?.profile?.bank_name ? ` · ${me.profile.bank_name} ${bankMasked}` : ""}
                  </div>
                  <div className="flex items-center gap-3 mt-3 text-xs text-emerald-200">
                    <span>Gross {INR(gross)}</span>
                    <span className="text-emerald-400">−</span>
                    <span>Ded. {INR(ded)}</span>
                    {reimb > 0 && (
                      <>
                        <span className="text-emerald-400">+</span>
                        <span>Reimb. {INR(reimb)}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-extrabold text-white tracking-tight">{INR(net)}</div>
                  <div className="text-emerald-200 text-xs mt-1">In Hand</div>
                </div>
              </div>
              <div className="h-1.5 flex">
                <div className="bg-white/30" style={{ width: `${gross + ded > 0 ? Math.round((gross / (gross + ded)) * 100) : 50}%` }} />
                <div className="bg-red-400/60 flex-1" />
              </div>
            </div>

            {/* Footer */}
            <div className="text-center text-[11px] text-gray-400 pb-5">
              This is a computer-generated payslip and does not require a signature.
              {company?.official_phone && (
                <> For queries contact HR at <span className="text-blue-600">{company.official_phone}</span>.</>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
