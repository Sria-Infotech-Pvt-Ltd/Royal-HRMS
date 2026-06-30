"use client";

import { useState } from "react";
import { EMP_DATA, grossEarnings, totalDeductions, netSalary, fmt } from "./payrollData";

interface Props { onNext: () => void; onBack: () => void; }

type SlipStatus = "pending" | "generated" | "emailed";

const STATUS_STYLE: Record<SlipStatus, { bg: string; text: string; label: string }> = {
  pending:   { bg: "bg-amber-50",   text: "text-amber-700",   label: "Pending"   },
  generated: { bg: "bg-blue-50",    text: "text-blue-700",    label: "Generated" },
  emailed:   { bg: "bg-emerald-50", text: "text-emerald-700", label: "Emailed"   },
};

export default function PayslipsStep({ onNext, onBack }: Props) {
  const [statuses, setStatuses] = useState<Record<string, SlipStatus>>(
    Object.fromEntries(EMP_DATA.map(e => [e.id, "pending"]))
  );
  const [generating, setGenerating] = useState(false);

  function generateAll() {
    setGenerating(true);
    setTimeout(() => {
      setStatuses(Object.fromEntries(EMP_DATA.map(e => [e.id, "generated"])));
      setGenerating(false);
    }, 1200);
  }

  function emailAll() {
    setStatuses(Object.fromEntries(EMP_DATA.map(e => [e.id, "emailed"])));
  }

  function emailOne(id: string) {
    setStatuses(p => ({ ...p, [id]: "emailed" }));
  }

  const generatedCount = Object.values(statuses).filter(s => s !== "pending").length;
  const allGenerated   = generatedCount === EMP_DATA.length;
  const totalNet       = EMP_DATA.reduce((s, e) => s + netSalary(e), 0);

  return (
    <div className="flex flex-col gap-4">

      {/* Header card */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
              <i className="ti ti-file-invoice text-blue-800 text-lg" />
            </div>
            <div>
              <div className="font-semibold text-gray-900">Generate Payslips</div>
              <div className="text-xs text-gray-500">June 2026 · {EMP_DATA.length} employees</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">
              Net Payable: <span className="font-bold text-emerald-700">{fmt(totalNet)}</span>
            </span>
            {allGenerated && (
              <button
                onClick={emailAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-blue-800 text-blue-800 rounded-lg hover:bg-blue-50 transition-colors"
              >
                <i className="ti ti-mail text-sm" /> Email All
              </button>
            )}
            <button
              onClick={generateAll}
              disabled={generating || allGenerated}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {generating
                ? <><i className="ti ti-loader-2 animate-spin text-sm" /> Generating...</>
                : allGenerated
                ? <><i className="ti ti-check text-sm" /> All Generated</>
                : <><i className="ti ti-file-plus text-sm" /> Generate All</>}
            </button>
            <span className="text-[10px] font-semibold bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Step 7 of 8</span>
          </div>
        </div>

        {/* Success banner */}
        {allGenerated && (
          <div className="flex items-center gap-2 px-5 py-3 bg-emerald-50 border-b border-emerald-100 text-sm text-emerald-700">
            <i className="ti ti-circle-check text-base" />
            All {EMP_DATA.length} payslips generated. Download or email them below.
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-5 py-3">Employee</th>
                <th className="text-right text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Gross Salary</th>
                <th className="text-right text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Deductions</th>
                <th className="text-right text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Net Salary</th>
                <th className="text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Status</th>
                <th className="text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {EMP_DATA.map(e => {
                const gross  = grossEarnings(e);
                const ded    = totalDeductions(e);
                const net    = netSalary(e);
                const status = statuses[e.id];
                const style  = STATUS_STYLE[status];
                return (
                  <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-800 text-white flex items-center justify-center text-xs font-bold shrink-0">
                          {e.avatar}
                        </div>
                        <div>
                          <div className="font-semibold text-sm text-gray-900">{e.name}</div>
                          <div className="text-[11px] text-gray-500">{e.designation}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-right font-semibold text-sm text-gray-800">{fmt(gross)}</td>
                    <td className="px-4 py-3.5 text-right text-sm font-medium text-red-600">{fmt(ded)}</td>
                    <td className="px-4 py-3.5 text-right font-bold text-emerald-700">{fmt(net)}</td>
                    <td className="px-4 py-3.5">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${style.bg} ${style.text}`}>
                        {style.label}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5">
                        <button
                          disabled={status === "pending"}
                          className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          title="Download PDF"
                        >
                          <i className="ti ti-download text-sm" />
                        </button>
                        <button
                          disabled={status === "pending"}
                          onClick={() => emailOne(e.id)}
                          className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          title="Email Payslip"
                        >
                          <i className="ti ti-mail text-sm" />
                        </button>
                        <button
                          disabled={status === "pending"}
                          className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          title="Preview"
                        >
                          <i className="ti ti-eye text-sm" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="bg-gray-50 border-t-2 border-gray-200">
                <td className="px-5 py-3 font-bold text-sm text-gray-900">Total</td>
                <td className="px-4 py-3 text-right font-bold text-sm text-gray-900">{fmt(EMP_DATA.reduce((s, e) => s + grossEarnings(e), 0))}</td>
                <td className="px-4 py-3 text-right font-bold text-sm text-red-600">{fmt(EMP_DATA.reduce((s, e) => s + totalDeductions(e), 0))}</td>
                <td className="px-4 py-3 text-right font-bold text-emerald-700">{fmt(totalNet)}</td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-100 bg-gray-50">
          <span className="text-xs text-gray-500">{generatedCount} of {EMP_DATA.length} payslips generated</span>
          <div className="flex items-center gap-2">
            <button onClick={onBack} className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors">
              <i className="ti ti-arrow-left text-sm" /> Back
            </button>
            <button
              onClick={onNext}
              disabled={!allGenerated}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continue <i className="ti ti-arrow-right text-sm" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
