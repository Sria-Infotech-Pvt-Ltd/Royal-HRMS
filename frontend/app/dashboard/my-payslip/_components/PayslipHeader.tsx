"use client";

import type { ApiPayslip } from "./types";
import { fmtMonth } from "./types";
import { logPayslipDownload } from "./downloadAudit";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";

interface Props {
  payslips: ApiPayslip[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  activeSlip: ApiPayslip | null;
}

export default function PayslipHeader({ payslips, selectedId, onSelect, activeSlip }: Props) {
  const activeId = selectedId ?? payslips[0]?.id ?? "";

  return (
    <div className="flex items-start justify-between flex-wrap gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>Payslips &amp; tax</h1>
        <p className="text-sm mt-1" style={{ color: "var(--on-variant)" }}>
          Understand your salary, deductions, taxes and employer contributions.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <select
          className="field-input field-select"
          value={activeId}
          onChange={e => onSelect(e.target.value)}
          aria-label="Select payslip month"
        >
          {payslips.map(p => (
            <option key={p.id} value={p.id}>{fmtMonth(p.cycle_start)}</option>
          ))}
        </select>

        {activeSlip ? (
          <a
            href={`${API_BASE}${API.payroll.payslipPdf(activeSlip.id)}`}
            className="btn btn-filled"
            onClick={() => logPayslipDownload(activeSlip.id)}
          >
            <i className="ti ti-download text-sm" /> Download payslip
          </a>
        ) : (
          <button
            disabled
            className="btn btn-filled disabled:opacity-50 disabled:cursor-not-allowed"
            title="No payslip selected"
          >
            <i className="ti ti-download text-sm" /> Download payslip
          </button>
        )}
      </div>
    </div>
  );
}
