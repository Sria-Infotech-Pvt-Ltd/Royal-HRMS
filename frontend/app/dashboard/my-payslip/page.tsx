"use client";

import { useState } from "react";

const EMPLOYEE = {
  name:        "Arjun Mehta",
  id:          "EMP-0042",
  dept:        "Engineering",
  designation: "Senior Software Developer",
  doj:         "14 Mar 2022",
  pan:         "ABCPM1234X",
  uan:         "100987654321",
  bank:        "HDFC Bank",
  account:     "XXXX4521",
  ifsc:        "HDFC0001234",
  avatar:      "AM",
};

const COMPANY = {
  name:    "Royal Staffing Services LLP",
  address: "4th Floor, Tech Park, Whitefield, Bengaluru — 560066",
  cin:     "U74999KA2018PTC099876",
};

type MonthKey = "jun" | "may" | "apr" | "mar";

const PAYSLIPS: Record<MonthKey, {
  month: string; year: string; salary_date: string;
  working_days: number; paid_days: number; lop: number;
  basic: number; hra: number; da: number; special: number; bonus: number; ot: number;
  pf: number; esi: number; pt: number; tds: number; loan: number; advance: number;
}> = {
  jun: { month: "June",  year: "2026", salary_date: "30 Jun 2026", working_days: 26, paid_days: 26, lop: 0,    basic: 45000, hra: 18000, da: 4500, special: 6000, bonus: 5000, ot: 2000, pf: 5400, esi: 0, pt: 200, tds: 3500, loan: 5000, advance: 0    },
  may: { month: "May",   year: "2026", salary_date: "30 May 2026", working_days: 26, paid_days: 25, lop: 1731, basic: 45000, hra: 18000, da: 4500, special: 6000, bonus: 0,    ot: 0,    pf: 5400, esi: 0, pt: 200, tds: 3500, loan: 5000, advance: 0    },
  apr: { month: "April", year: "2026", salary_date: "30 Apr 2026", working_days: 27, paid_days: 27, lop: 0,    basic: 45000, hra: 18000, da: 4500, special: 6000, bonus: 0,    ot: 1500, pf: 5400, esi: 0, pt: 200, tds: 3500, loan: 5000, advance: 2000 },
  mar: { month: "March", year: "2026", salary_date: "31 Mar 2026", working_days: 26, paid_days: 26, lop: 0,    basic: 45000, hra: 18000, da: 4500, special: 6000, bonus: 0,    ot: 0,    pf: 5400, esi: 0, pt: 200, tds: 3500, loan: 5000, advance: 0    },
};

function fmt(n: number) { return "₹" + n.toLocaleString("en-IN"); }

function EarningRow({ label, value, dimZero }: { label: string; value: number; dimZero?: boolean }) {
  if (dimZero && value === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-semibold text-gray-800">{value > 0 ? fmt(value) : "—"}</span>
    </div>
  );
}

function DeductionRow({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  if (value === 0) return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-sm font-semibold ${highlight ? "text-red-600" : "text-red-500"}`}>{fmt(value)}</span>
    </div>
  );
}

export default function MyPayslipPage() {
  const [selected, setSelected] = useState<MonthKey>("jun");
  const slip = PAYSLIPS[selected];

  const gross = slip.basic + slip.hra + slip.da + slip.special + slip.bonus + slip.ot;
  const ded   = slip.pf + slip.esi + slip.pt + slip.tds + slip.loan + slip.advance + slip.lop;
  const reimb = 4000; // travel + medical + internet + food
  const net   = gross - ded + reimb;

  return (
    <div className="flex flex-col gap-6">

      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">My Payslips</h1>
          <p className="text-sm text-gray-500 mt-1">View and download your monthly salary statements</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
            <i className="ti ti-mail text-sm" /> Email Payslip
          </button>
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors">
            <i className="ti ti-download text-sm" /> Download PDF
          </button>
        </div>
      </div>

      <div className="flex gap-6 items-start">

        {/* ── Sidebar ── */}
        <div className="flex flex-col gap-4 w-56 shrink-0">

          {/* Employee card */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-br from-blue-900 to-blue-700 p-4 text-center">
              <div className="w-14 h-14 rounded-full bg-white/20 border-2 border-white/40 text-white font-bold text-xl flex items-center justify-center mx-auto mb-2">
                {EMPLOYEE.avatar}
              </div>
              <div className="text-white font-semibold text-sm">{EMPLOYEE.name}</div>
              <div className="text-blue-200 text-xs mt-0.5">{EMPLOYEE.designation}</div>
              <div className="text-blue-300 text-[11px] mt-0.5">{EMPLOYEE.id}</div>
            </div>
            <div className="p-3 divide-y divide-gray-100">
              {[
                ["Department", EMPLOYEE.dept],
                ["Date of Join", EMPLOYEE.doj],
                ["PAN", EMPLOYEE.pan],
                ["UAN", EMPLOYEE.uan],
              ].map(([k, v]) => (
                <div key={k} className="flex flex-col py-2">
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider">{k}</span>
                  <span className="text-xs font-semibold text-gray-800 mt-0.5">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Month selector */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Select Month</span>
            </div>
            <div className="py-1">
              {(Object.keys(PAYSLIPS) as MonthKey[]).map(key => {
                const s      = PAYSLIPS[key];
                const active = selected === key;
                return (
                  <button
                    key={key}
                    onClick={() => setSelected(key)}
                    className={`w-full text-left px-4 py-2.5 flex items-center justify-between border-l-2 transition-colors ${
                      active ? "border-blue-800 bg-blue-50" : "border-transparent hover:bg-gray-50"
                    }`}
                  >
                    <div>
                      <div className={`text-sm font-semibold ${active ? "text-blue-800" : "text-gray-700"}`}>
                        {s.month} {s.year}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">{s.salary_date}</div>
                    </div>
                    <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">Paid</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Payslip document ── */}
        <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">

          {/* Company letterhead */}
          <div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-700 px-7 py-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-white font-bold text-lg leading-tight">{COMPANY.name}</div>
                <div className="text-blue-200 text-xs mt-1">{COMPANY.address}</div>
                <div className="text-blue-300 text-[11px] mt-0.5">CIN: {COMPANY.cin}</div>
              </div>
              <div className="text-right">
                <div className="text-white font-extrabold text-2xl tracking-wide">PAYSLIP</div>
                <div className="text-blue-200 text-sm mt-1 font-medium">{slip.month} {slip.year}</div>
                <div className="text-blue-300 text-xs mt-0.5">Salary Date: {slip.salary_date}</div>
              </div>
            </div>
          </div>

          {/* Employee details strip */}
          <div className="grid grid-cols-4 divide-x divide-gray-100 bg-gray-50 border-b border-gray-200">
            {[
              ["Employee ID",  EMPLOYEE.id],
              ["Bank",        EMPLOYEE.bank],
              ["Account No.", EMPLOYEE.account],
              ["IFSC Code",   EMPLOYEE.ifsc],
            ].map(([label, value]) => (
              <div key={label} className="px-5 py-3">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{label}</div>
                <div className="text-xs font-semibold text-gray-800 font-mono">{value}</div>
              </div>
            ))}
          </div>

          {/* Attendance summary */}
          <div className="flex items-center gap-0 mx-6 mt-5 mb-5 rounded-xl overflow-hidden border border-gray-200">
            {[
              { label: "Working Days",  value: slip.working_days,  color: "text-gray-900", sub: "in June 2026" },
              { label: "Paid Days",     value: slip.paid_days,     color: "text-emerald-700", sub: "days credited" },
              { label: "Loss of Pay",   value: slip.lop > 0 ? 1 : 0, color: slip.lop > 0 ? "text-red-600" : "text-gray-400", sub: slip.lop > 0 ? fmt(slip.lop) + " deducted" : "no LOP" },
            ].map((item, i) => (
              <div key={i} className={`flex-1 text-center py-3 ${i < 2 ? "border-r border-gray-200" : ""} bg-white`}>
                <div className={`text-2xl font-extrabold ${item.color}`}>{item.value}</div>
                <div className="text-[11px] font-medium text-gray-600 mt-0.5">{item.label}</div>
                <div className="text-[10px] text-gray-400">{item.sub}</div>
              </div>
            ))}
          </div>

          {/* Earnings + Deductions two-column */}
          <div className="grid grid-cols-2 gap-0 mx-6 mb-5 rounded-xl overflow-hidden border border-gray-200">

            {/* Earnings */}
            <div className="border-r border-gray-200">
              <div className="flex items-center gap-2 px-4 py-3 bg-emerald-50 border-b border-emerald-100">
                <div className="w-1 h-4 rounded-full bg-emerald-600" />
                <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider">Earnings</span>
              </div>
              <div className="px-4 py-2">
                <EarningRow label="Basic Salary"              value={slip.basic} />
                <EarningRow label="House Rent Allowance (HRA)" value={slip.hra} />
                <EarningRow label="Dearness Allowance (DA)"   value={slip.da} />
                <EarningRow label="Special Allowance"         value={slip.special} />
                <EarningRow label="Bonus"                     value={slip.bonus} dimZero />
                <EarningRow label="Overtime"                  value={slip.ot} dimZero />
              </div>
              <div className="flex justify-between items-center px-4 py-3 bg-emerald-50 border-t border-emerald-100 mt-1">
                <span className="text-sm font-bold text-emerald-900">Gross Earnings</span>
                <span className="text-base font-extrabold text-emerald-700">{fmt(gross)}</span>
              </div>
            </div>

            {/* Deductions */}
            <div>
              <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border-b border-red-100">
                <div className="w-1 h-4 rounded-full bg-red-500" />
                <span className="text-xs font-bold text-red-800 uppercase tracking-wider">Deductions</span>
              </div>
              <div className="px-4 py-2">
                <DeductionRow label="Provident Fund (PF)"   value={slip.pf} />
                <DeductionRow label="ESI"                    value={slip.esi} />
                <DeductionRow label="Professional Tax (PT)"  value={slip.pt} />
                <DeductionRow label="TDS"                    value={slip.tds} />
                <DeductionRow label="Loan EMI"               value={slip.loan} />
                <DeductionRow label="Advance Recovery"       value={slip.advance} />
                <DeductionRow label="Loss of Pay (LOP)"      value={slip.lop} highlight />
              </div>
              <div className="flex justify-between items-center px-4 py-3 bg-red-50 border-t border-red-100 mt-1">
                <span className="text-sm font-bold text-red-900">Total Deductions</span>
                <span className="text-base font-extrabold text-red-600">{fmt(ded)}</span>
              </div>
            </div>
          </div>

          {/* Reimbursements */}
          <div className="mx-6 mb-5 rounded-xl border border-blue-100 bg-blue-50 overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-blue-100">
              <i className="ti ti-receipt text-blue-700 text-sm" />
              <span className="text-xs font-bold text-blue-800 uppercase tracking-wider">Reimbursements</span>
              <span className="ml-auto text-sm font-bold text-blue-700">{fmt(reimb)}</span>
            </div>
            <div className="flex items-center divide-x divide-blue-100 px-0">
              {[["Travel","₹2,000"],["Medical","₹500"],["Internet","₹500"],["Food","₹1,000"]].map(([k,v]) => (
                <div key={k} className="flex-1 text-center py-2.5">
                  <div className="text-[10px] text-blue-500 uppercase tracking-wider">{k}</div>
                  <div className="text-sm font-bold text-blue-800 mt-0.5">{v}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Net salary banner */}
          <div className="mx-6 mb-6 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4">
              <div>
                <div className="text-emerald-100 text-sm font-medium">Net Salary Credited</div>
                <div className="text-white text-xs mt-1 opacity-80">
                  Paid on {slip.salary_date} · {EMPLOYEE.bank} {EMPLOYEE.account}
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-emerald-200">
                  <span>Gross {fmt(gross)}</span>
                  <span className="text-emerald-400">−</span>
                  <span>Ded. {fmt(ded)}</span>
                  <span className="text-emerald-400">+</span>
                  <span>Reimb. {fmt(reimb)}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-4xl font-extrabold text-white tracking-tight">{fmt(net)}</div>
                <div className="text-emerald-200 text-xs mt-1">In Hand</div>
              </div>
            </div>

            {/* Mini breakdown bar */}
            <div className="h-1.5 flex">
              <div className="bg-white/30" style={{ width: `${Math.round((gross / (gross + ded)) * 100)}%` }} />
              <div className="bg-red-400/60 flex-1" />
            </div>
          </div>

          {/* Footer note */}
          <div className="text-center text-[11px] text-gray-400 pb-5">
            This is a computer-generated payslip and does not require a signature.
            For queries, contact HR at <span className="text-blue-600">hr@royalstaffing.in</span>
          </div>
        </div>
      </div>
    </div>
  );
}
