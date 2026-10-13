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
  if (totalCount <= 0) return null;

  const rangeStart = (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, totalCount);
  const lastPage = Math.max(totalPages, 1);

  return (
    <div className="pager">
      <span className="txt">Showing {rangeStart}–{rangeEnd} of {totalCount} {itemLabel}</span>
      <div className="pgbtns">
        <button className="pgbtn" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)} suppressHydrationWarning>‹ Prev</button>
        {Array.from({ length: lastPage }, (_, index) => index + 1).map(number => (
          <button key={number} type="button" className={`pgbtn${number === page ? " on" : ""}`} onClick={() => onPageChange(number)} suppressHydrationWarning>
            {number}
          </button>
        ))}
        <button className="pgbtn" type="button" disabled={page >= lastPage} onClick={() => onPageChange(page + 1)} suppressHydrationWarning>Next ›</button>
      </div>
    </div>
  );
}
