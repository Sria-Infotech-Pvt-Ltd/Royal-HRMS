"use client";

// ── Types ──────────────────────────────────────────────────────────────────────

export type RuleType = "percent" | "fixed" | "slab" | "variable";

export interface PayrollRule {
  id: string;
  name: string;
  type: RuleType;
  value: number;
  basis: string;
  effectiveDate: string;
  enabled: boolean;
  statutory: boolean;
}

// ── Seed data ──────────────────────────────────────────────────────────────────

export const EARNING_RULES: PayrollRule[] = [
  { id: "basic",      name: "Basic Salary",          type: "percent",  value: 40,   basis: "% of CTC",      effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "hra",        name: "HRA",                   type: "percent",  value: 50,   basis: "% of Basic",    effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "da",         name: "Dearness Allowance",    type: "percent",  value: 15,   basis: "% of Basic",    effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "special",    name: "Special Allowance",     type: "percent",  value: 10,   basis: "% of Basic",    effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "conveyance", name: "Conveyance Allowance",  type: "fixed",    value: 1600, basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "medical",    name: "Medical Allowance",     type: "fixed",    value: 1250, basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "travel",     name: "Travel Allowance",      type: "fixed",    value: 2000, basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "internet",   name: "Internet Allowance",    type: "fixed",    value: 500,  basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: false, statutory: false },
  { id: "incentive",  name: "Incentives",            type: "variable", value: 0,    basis: "Performance",   effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "overtime",   name: "Overtime",              type: "fixed",    value: 0,    basis: "Per OT Hour",   effectiveDate: "2025-04-01", enabled: true,  statutory: false },
];

export const DEDUCTION_RULES: PayrollRule[] = [
  { id: "pf",       name: "Provident Fund (PF)",     type: "percent",  value: 12,   basis: "% of Basic",    effectiveDate: "2025-04-01", enabled: true,  statutory: true  },
  { id: "esi",      name: "ESI",                     type: "percent",  value: 0.75, basis: "% of Gross",    effectiveDate: "2025-04-01", enabled: true,  statutory: true  },
  { id: "pt",       name: "Professional Tax",        type: "fixed",    value: 200,  basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: true,  statutory: true  },
  { id: "tds",      name: "Income Tax (TDS)",        type: "slab",     value: 0,    basis: "Annual Slab",   effectiveDate: "2025-04-01", enabled: true,  statutory: true  },
  { id: "lwf",      name: "Labour Welfare Fund",     type: "fixed",    value: 25,   basis: "Fixed / Month", effectiveDate: "2025-04-01", enabled: true,  statutory: true  },
  { id: "loan_emi", name: "Loan EMI",                type: "fixed",    value: 0,    basis: "Per Loan",      effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "advance",  name: "Salary Advance Recovery", type: "fixed",    value: 0,    basis: "Per Recovery",  effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "lop",      name: "Loss of Pay (LOP)",       type: "variable", value: 0,    basis: "Per Day",       effectiveDate: "2025-04-01", enabled: true,  statutory: false },
  { id: "other",    name: "Other Deductions",        type: "fixed",    value: 0,    basis: "Configurable",  effectiveDate: "2025-04-01", enabled: false, statutory: false },
];

// ── Shared helpers ─────────────────────────────────────────────────────────────

export const TYPE_BADGE: Record<RuleType, { label: string; cls: string }> = {
  percent:  { label: "Percentage",   cls: "bg-blue-50 text-blue-800"     },
  fixed:    { label: "Fixed Amount", cls: "bg-violet-50 text-violet-700" },
  slab:     { label: "Slab-based",   cls: "bg-amber-50 text-amber-700"   },
  variable: { label: "Variable",     cls: "bg-gray-100 text-gray-600"    },
};

export function fmtValue(r: PayrollRule): string {
  if (r.type === "percent" )  return `${r.value}%`;
  if (r.type === "fixed" && r.value > 0) return `₹${r.value.toLocaleString("en-IN")}`;
  if (r.type === "slab")      return "As per slab";
  return "Variable";
}

// ── Component ──────────────────────────────────────────────────────────────────

interface Props {
  rules: PayrollRule[];
  onToggle: (id: string) => void;
  onEdit: (rule: PayrollRule) => void;
}

const HEADERS = ["Component", "Type", "Value", "Applies On", "Effective Date", "Statutory", "Status", ""];

export default function RulesTable({ rules, onToggle, onEdit }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            {HEADERS.map(h => (
              <th key={h} className="text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rules.map(rule => (
            <tr key={rule.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3.5">
                <span className="font-semibold text-gray-900">{rule.name}</span>
              </td>
              <td className="px-4 py-3.5">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${TYPE_BADGE[rule.type].cls}`}>
                  {TYPE_BADGE[rule.type].label}
                </span>
              </td>
              <td className="px-4 py-3.5 font-semibold text-gray-800">{fmtValue(rule)}</td>
              <td className="px-4 py-3.5 text-gray-500 text-[12px]">{rule.basis}</td>
              <td className="px-4 py-3.5 text-gray-500 text-[12px]">{rule.effectiveDate}</td>
              <td className="px-4 py-3.5">
                {rule.statutory
                  ? <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded"><i className="ti ti-shield-check text-xs" /> Yes</span>
                  : <span className="text-[11px] text-gray-400">—</span>}
              </td>
              <td className="px-4 py-3.5">
                <button
                  onClick={() => onToggle(rule.id)}
                  title={rule.enabled ? "Enabled — click to disable" : "Disabled — click to enable"}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${rule.enabled ? "bg-blue-800" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${rule.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                </button>
              </td>
              <td className="px-4 py-3.5">
                <button
                  onClick={() => onEdit(rule)}
                  className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 transition-colors"
                  title="Edit rule"
                >
                  <i className="ti ti-edit text-sm" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
