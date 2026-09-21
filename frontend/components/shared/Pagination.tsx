"use client";

// Generic page-number pagination — pairs with any backend list endpoint
// using core.pagination's PageNumberPagination (page_size=20 convention).
// Only renders once there's more than one page; a single real page of
// data legitimately has nothing to paginate, so this stays hidden rather
// than showing an inert "page 1 of 1" control.

interface Props {
  page: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  itemLabel: string;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, totalPages, totalCount, pageSize, itemLabel, onPageChange }: Props) {
  if (totalPages <= 1) return null;

  const rangeStart = (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, totalCount);

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, flexWrap: "wrap", gap: 8 }}>
      <span style={{ fontSize: 13, color: "var(--on-variant)" }}>
        Showing {rangeStart}–{rangeEnd} of {totalCount} {itemLabel}
      </span>
      <div style={{ display: "flex", gap: 4 }}>
        <button
          className="btn btn-ghost btn-sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          suppressHydrationWarning
        >
          <i className="ti ti-chevron-left" /> Prev
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
          <button
            key={p}
            className={`btn btn-sm ${p === page ? "btn-filled" : "btn-ghost"}`}
            onClick={() => onPageChange(p)}
            suppressHydrationWarning
          >
            {p}
          </button>
        ))}
        <button
          className="btn btn-ghost btn-sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          suppressHydrationWarning
        >
          Next <i className="ti ti-chevron-right" />
        </button>
      </div>
    </div>
  );
}
