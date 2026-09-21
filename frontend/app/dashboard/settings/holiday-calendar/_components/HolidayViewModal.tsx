"use client";

import type { Holiday } from "@/types/holidays";

const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const TYPE_DOT: Record<string, string> = {
  national: "bg-[var(--info)]", regional: "bg-teal-500", company: "bg-[var(--warn)]",
};

function fmtDate(iso: string) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${parseInt(d)} ${MONTH_SHORT[parseInt(m) - 1]} ${y}`;
}

interface Props {
  holiday: Holiday;
  onClose: () => void;
  onEdit:  () => void;
}

export default function HolidayViewModal({ holiday, onClose, onEdit }: Props) {
  const rows: [string, string][] = [
    ["Date",    fmtDate(holiday.date)],
    ["Day",     holiday.day],
    ["Type",    holiday.holiday_type_display],
    ["Applies", holiday.mandatory_optional],
    ["Status",  holiday.is_active ? "Active" : "Inactive"],
    ["Branch",  holiday.branch_name],
  ];

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-[var(--surface)] rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--outline-v)]">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${TYPE_DOT[holiday.holiday_type]}`} />
            <span className="text-sm font-bold text-[var(--on-bg)]">{holiday.name}</span>
          </div>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--bg-mid)] text-[var(--outline)] transition-colors">
            <i className="ti ti-x text-sm" />
          </button>
        </div>
        <div className="px-6 py-5 grid grid-cols-2 gap-4">
          {rows.map(([label, value]) => (
            <div key={label}>
              <div className="text-xs text-[var(--outline)] mb-0.5">{label}</div>
              <div className="text-sm font-semibold text-[var(--on-bg)]">{value}</div>
            </div>
          ))}
          {holiday.description && (
            <div className="col-span-2">
              <div className="text-xs text-[var(--outline)] mb-0.5">Description</div>
              <div className="text-sm text-[var(--on-bg)]">{holiday.description}</div>
            </div>
          )}
        </div>
        <div className="flex gap-2 px-6 pb-5">
          <button onClick={onEdit}
            className="flex-1 py-2 rounded-xl border border-[var(--outline-v)] text-sm font-medium text-[var(--on-variant)] hover:bg-[var(--bg-mid)] transition-colors flex items-center justify-center gap-2">
            <i className="ti ti-edit" /> Edit
          </button>
          <button onClick={onClose}
            className="flex-1 py-2 rounded-xl bg-[var(--info)] text-white text-sm font-medium hover:bg-[var(--info)] transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
