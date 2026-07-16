"use client";

import type { Holiday, HolidayType } from "@/types/holidays";

const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(iso: string) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${parseInt(d)} ${MONTH_SHORT[parseInt(m) - 1]} ${y}`;
}

export const TYPE_STYLES: Record<HolidayType, { badge: string; pill: string; cal: string; dot: string }> = {
  national: { badge: "bg-blue-100 text-blue-700",   pill: "bg-blue-600",   cal: "bg-blue-50 border-l-2 border-blue-400 text-blue-800",   dot: "bg-blue-500"  },
  regional: { badge: "bg-teal-100 text-teal-700",   pill: "bg-teal-600",   cal: "bg-teal-50 border-l-2 border-teal-400 text-teal-800",   dot: "bg-teal-500"  },
  company:  { badge: "bg-amber-100 text-amber-700", pill: "bg-amber-500",  cal: "bg-amber-50 border-l-2 border-amber-400 text-amber-800", dot: "bg-amber-500" },
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
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-400">
          <i className="ti ti-calendar-off text-5xl text-gray-300" />
          <p className="text-sm font-medium">{loading ? "Loading holidays…" : `No holidays found for ${year}`}</p>
          {!loading && <button onClick={onAdd} className="mt-1 text-sm text-blue-600 hover:underline">+ Add the first holiday</button>}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  {["Holiday Name","Date","Day","Holiday Type","Mandatory / Optional","Applicable Branches","Status","Actions"].map(col => (
                    <th key={col} className="px-4 py-3 text-left text-xs font-bold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((h, idx) => (
                  <tr key={h.id} className={`transition-colors hover:bg-gray-50 ${idx < pageRows.length - 1 ? "border-b border-gray-100" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_STYLES[h.holiday_type].dot}`} />
                        <span className="font-semibold text-gray-800 text-sm">{h.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{fmtDate(h.date)}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">{h.day}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${TYPE_STYLES[h.holiday_type].badge}`}>
                        {h.holiday_type_display}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {h.is_optional
                        ? <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-700">{h.mandatory_optional}</span>
                        : <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">{h.mandatory_optional}</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-[160px] truncate">{h.branch_name}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => onToggleActive(h)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold transition-colors ${h.is_active ? "bg-green-100 text-green-700 hover:bg-green-200" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${h.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                        {h.is_active ? "Active" : "Inactive"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <button onClick={() => onView(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors">
                          <i className="ti ti-eye text-xs" />
                        </button>
                        <button onClick={() => onEdit(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors">
                          <i className="ti ti-edit text-xs" />
                        </button>
                        <button onClick={() => onDelete(h)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:border-red-400 hover:text-red-600 transition-colors">
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
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50">
              <span className="text-xs text-gray-500">
                Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filtered.length)} of {filtered.length}
              </span>
              <div className="flex items-center gap-1">
                <button onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page === 1}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 hover:border-blue-400 hover:text-blue-600 transition-colors">
                  <i className="ti ti-chevron-left text-xs" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => onPageChange(p)}
                    className={`w-7 h-7 flex items-center justify-center rounded-lg text-xs font-semibold transition-colors ${p === page ? "bg-blue-700 text-white border border-blue-700" : "border border-gray-200 text-gray-500 hover:border-blue-400 hover:text-blue-600"}`}>
                    {p}
                  </button>
                ))}
                <button onClick={() => onPageChange(Math.min(totalPages, page + 1))} disabled={page === totalPages}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 hover:border-blue-400 hover:text-blue-600 transition-colors">
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
