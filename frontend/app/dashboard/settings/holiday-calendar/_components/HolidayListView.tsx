"use client";

import type { Holiday, HolidayType } from "@/types/holidays";

const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(iso: string) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${parseInt(d)} ${MONTH_SHORT[parseInt(m) - 1]} ${y}`;
}

export const TYPE_STYLES: Record<HolidayType, { badge: string; pill: string; cal: string; dot: string }> = {
  national: { badge: "bg-[var(--info-c)] text-[var(--info)]",   pill: "bg-[var(--info)]",   cal: "bg-[var(--info-c)] border-l-2 border-[var(--info)] text-[var(--info)]",   dot: "bg-[var(--info)]"  },
  regional: { badge: "bg-teal-100 text-teal-700",   pill: "bg-teal-600",   cal: "bg-teal-50 border-l-2 border-teal-400 text-teal-800",   dot: "bg-teal-500"  },
  company:  { badge: "bg-[var(--warn-c)] text-[var(--warn)]", pill: "bg-[var(--warn)]",  cal: "bg-[var(--warn-c)] border-l-2 border-[var(--warn)] text-[var(--warn)]", dot: "bg-[var(--warn)]" },
};

interface Props {
  loading:      boolean;
  filtered:     Holiday[];
  pageRows:     Holiday[];
  page:         number;
  totalPages:   number;
  pageSize:     number;
  year:         number;
  onPageChange: (page: number) => void;
  onAdd:        () => void;
  onView:       (h: Holiday) => void;
  onEdit:       (h: Holiday) => void;
  onDelete:     (h: Holiday) => void;
  onToggleActive: (h: Holiday) => void;
}

export default function HolidayListView({
  loading, filtered, pageRows, page, totalPages, pageSize, year,
  onPageChange, onAdd, onView, onEdit, onDelete, onToggleActive,
}: Props) {
  return (
    <div className="bg-[var(--surface)] rounded-2xl border border-[var(--outline-v)] shadow-sm overflow-hidden">
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-[var(--outline)]">
          <i className="ti ti-calendar-off text-5xl text-[var(--outline)]" />
          <p className="text-sm font-medium">{loading ? "Loading holidays…" : `No holidays found for ${year}`}</p>
          {!loading && <button onClick={onAdd} className="mt-1 text-sm text-[var(--info)] hover:underline">+ Add the first holiday</button>}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-[var(--bg-mid)] border-b border-[var(--outline-v)]">
                  {["Holiday Name","Date","Day","Holiday Type","Mandatory / Optional","Applicable Company Codes","Status","Actions"].map(col => (
                    <th key={col} className="px-4 py-3 text-left text-xs font-bold text-[var(--outline)] uppercase tracking-wider whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((h, idx) => (
                  <tr key={h.id} className={`transition-colors hover:bg-[var(--bg-mid)] ${idx < pageRows.length - 1 ? "border-b border-[var(--outline-v)]" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_STYLES[h.holiday_type].dot}`} />
                        <span className="font-semibold text-[var(--on-bg)] text-sm">{h.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--on-bg)] whitespace-nowrap">{fmtDate(h.date)}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-medium text-[var(--on-variant)] bg-[var(--bg-mid)] px-2 py-0.5 rounded">{h.day}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${TYPE_STYLES[h.holiday_type].badge}`}>
                        {h.holiday_type_display}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {h.is_optional
                        ? <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--primary-c)] text-[var(--primary)]">{h.mandatory_optional}</span>
                        : <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--success-c)] text-[var(--success)]">{h.mandatory_optional}</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--on-variant)] max-w-[160px] truncate">{h.branch_name}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => onToggleActive(h)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold transition-colors ${h.is_active ? "bg-[var(--success-c)] text-[var(--success)] hover:bg-[var(--success-c)]" : "bg-[var(--bg-mid)] text-[var(--on-variant)] hover:bg-[var(--bg-mid)]"}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${h.is_active ? "bg-[var(--success)]" : "bg-[var(--outline)]"}`} />
                        {h.is_active ? "Active" : "Inactive"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <button onClick={() => onView(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
                          <i className="ti ti-eye text-xs" />
                        </button>
                        <button onClick={() => onEdit(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
                          <i className="ti ti-edit text-xs" />
                        </button>
                        <button onClick={() => onDelete(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] hover:border-[var(--error)] hover:text-[var(--error)] transition-colors">
                          <i className="ti ti-trash text-xs" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--outline-v)] bg-[var(--bg-mid)]">
              <span className="text-xs text-[var(--on-variant)]">
                Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filtered.length)} of {filtered.length}
              </span>
              <div className="flex items-center gap-1">
                <button onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page === 1}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] disabled:opacity-40 hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
                  <i className="ti ti-chevron-left text-xs" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => onPageChange(p)}
                    className={`w-7 h-7 flex items-center justify-center rounded-lg text-xs font-semibold transition-colors ${p === page ? "bg-[var(--info)] text-white border border-[var(--info)]" : "border border-[var(--outline-v)] text-[var(--on-variant)] hover:border-[var(--info)] hover:text-[var(--info)]"}`}>
                    {p}
                  </button>
                ))}
                <button onClick={() => onPageChange(Math.min(totalPages, page + 1))} disabled={page === totalPages}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] disabled:opacity-40 hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
                  <i className="ti ti-chevron-right text-xs" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
