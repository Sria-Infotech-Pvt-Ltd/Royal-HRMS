"use client";

// The branded payslip document — shared by My Payslips (employee) and the HR
// payslip view (Payroll → run → employee). Renders the SAVED payslip values
// only; nothing is recalculated here. Zero amounts are hidden from the
// breakdown rows (as before) but totals always show, including ₹0.

export interface PayslipDocData {
  cycle_start: string;
  pay_date: string;
  basic: string;
  hra: string;
  special_allowance: string;
  bonus: string;
  other_earnings: Record<string, number>;
  other_deductions?: Record<string, number>;
  reimbursements: string;
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
}

export interface PayslipCompany {
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

export const INR = (n: string | number) =>
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

export const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

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

export default function PayslipDocument({
  slip, company, strip, netLabel = "Net Salary Credited", netSubline, className = "",
}: {
  slip: PayslipDocData;
  company: PayslipCompany | null | undefined;
  /** The four label/value cells under the letterhead (e.g. Employee ID, bank details). */
  strip: [string, string][];
  netLabel?: string;
  /** Line under the net amount label, e.g. "Paid on 30 Sept 2026 · HDFC ••••1234". */
  netSubline: string;
  className?: string;
}) {
  const gross  = Number(slip.gross_earnings  ?? 0);
  const ded    = Number(slip.total_deductions ?? 0);
  const net    = Number(slip.net_pay         ?? 0);
  const reimb  = Number(slip.reimbursements  ?? 0);
  const lopAmt = Number(slip.lop_deduction   ?? 0);
  const lopDays = Number(slip.lop_days ?? 0);
  const companyAddress = company
    ? [company.address, company.city, company.state, company.pin_code].filter(Boolean).join(", ")
    : "";

  return (
    <div className={`payslip-doc card flex-1 min-w-0 ${className}`} style={{ boxShadow: "var(--shadow)" }}>

      {/* Company letterhead */}
      <div className="px-7 py-6" style={{ background: "linear-gradient(to right, var(--primary), var(--primary), var(--primary-c))" }}>
        <div className="flex items-start justify-between">
          <div>
            {(company?.logo_url || company?.logo) && (
              // eslint-disable-next-line @next/next/no-img-element
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
        {strip.map(([label, value], idx) => (
          <div key={label} className="px-5 py-3 border-[var(--outline-v)]" style={{ borderLeftWidth: idx > 0 ? 1 : 0, borderLeftStyle: "solid" }}>
            <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: "var(--outline)" }}>{label}</div>
            <div className="text-xs font-semibold font-mono" style={{ color: "var(--on-bg)" }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Attendance summary */}
      <div className="flex items-center mx-6 mt-5 mb-5 rounded-xl overflow-hidden border" style={{ borderColor: "var(--outline-v)" }}>
        {[
          { label: "Working Days", value: slip.total_working_days, color: "var(--on-bg)", sub: fmtMonth(slip.cycle_start) },
          { label: "Paid Days", value: slip.total_working_days - lopDays, color: "var(--success)", sub: "days credited" },
          {
            label: "Loss of Pay",
            value: lopDays > 0 ? lopDays : 0,
            color: lopDays > 0 ? "var(--error)" : "var(--outline)",
            sub: lopDays > 0 ? `${INR(lopAmt)} deducted` : "no LOP",
          },
        ].map((item, i) => (
          <div key={i} className="flex-1 text-center py-3 border-[var(--outline-v)]" style={{ background: "#fff", borderRightWidth: i < 2 ? 1 : 0, borderRightStyle: "solid" }}>
            <div className="text-2xl font-extrabold" style={{ color: item.color }}>{item.value}</div>
            <div className="text-[11px] font-medium mt-0.5" style={{ color: "var(--on-variant)" }}>{item.label}</div>
            <div className="text-[10px]" style={{ color: "var(--outline)" }}>{item.sub}</div>
          </div>
        ))}
      </div>

      {/* Earnings + Deductions */}
      <div className="payslip-earn-ded grid grid-cols-2 gap-0 mx-6 mb-5 rounded-xl overflow-hidden border" style={{ borderColor: "var(--outline-v)" }}>
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
            {Object.entries(slip.other_deductions ?? {}).map(([name, amt]) => (
              <DeductionRow key={name} label={name} value={amt} />
            ))}
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
            <div className="text-sm font-medium" style={{ color: "rgba(255,255,255,0.85)" }}>{netLabel}</div>
            <div className="text-white text-xs mt-1 opacity-80">{netSubline}</div>
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

      <style jsx>{`
        @media (max-width: 560px) {
          .payslip-detail-strip { grid-template-columns: 1fr 1fr; }
          .payslip-earn-ded { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  );
}
