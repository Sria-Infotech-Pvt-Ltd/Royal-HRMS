"use client";

import Link from "next/link";
import { fmtDate, initials } from "../interview-list/_data";
import type { ApprovalUser } from "./_components/OnboardingDrawer";
import { isApprovedStatus, rangeLabel, statusMeta } from "./_filters";

interface ApprovalsTableProps {
  rows:           ApprovalUser[]
  /** How many submissions match the filters, across every page. */
  matching:       number
  page:           number
  pageSize:       number
  totalPages:     number
  onPageChange:   (page: number) => void
  isLoading:      boolean
  error:          string
  onRetry:        () => void
  hasFilters:     boolean
  onClearFilters: () => void
  canApprove:     boolean
  showBranch:     boolean
  onReview:       (row: ApprovalUser) => void
}

function Skeleton() {
  return (
    <div className="cand-skeleton" role="status" aria-label="Loading submissions">
      {[0, 1, 2, 3].map(row => (
        <div key={row} className="cand-skeleton-row">
          <span className="cand-skeleton-dot" /><span className="cand-skeleton-bar" /><span className="cand-skeleton-bar short" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ hasFilters, onClearFilters }: Pick<ApprovalsTableProps, "hasFilters" | "onClearFilters">) {
  return (
    <div className="empty-state cand-empty">
      <i className={`ti ${hasFilters ? "ti-search-off" : "ti-user-plus"}`} />
      <h3>{hasFilters ? "No submissions match your filters" : "No onboarding submissions yet"}</h3>
      <p>
        {hasFilters
          ? "Try a different search or status, or clear the filters to see everything."
          : "When a selected candidate completes the onboarding wizard, their submission will appear here for review."}
      </p>
      {hasFilters && (
        <button type="button" className="btn btn-ghost" onClick={onClearFilters}><i className="ti ti-filter-off" /> Clear filters</button>
      )}
    </div>
  );
}

function ActionCell({ row, canApprove, onReview }: { row: ApprovalUser; canApprove: boolean; onReview: (row: ApprovalUser) => void }) {
  if (row.onboarding_status === "rejected") {
    return <span className="badge badge-neutral" title="Waiting for the employee to correct and resubmit">Awaiting resubmission</span>;
  }
  if (isApprovedStatus(row.onboarding_status)) {
    // The review drawer is for deciding; an approved person has moved on to the employee list, so open their profile instead.
    return <Link className="btn btn-sm btn-ghost" href={`/dashboard/employees/${row.id}`}><i className="ti ti-user" /> Open profile</Link>;
  }
  if (!canApprove) return null;
  const isPending = row.onboarding_status === "submitted";
  return (
    <button type="button" className={`btn btn-sm ${isPending ? "btn-filled" : "btn-ghost"}`} onClick={() => onReview(row)}>
      <i className={`ti ${isPending ? "ti-clipboard-check" : "ti-eye"}`} /> {isPending ? "Review" : "View"}
    </button>
  );
}

/** The submissions list, with its own loading, error and empty states. */
export default function ApprovalsTable(props: ApprovalsTableProps) {
  const { rows, isLoading, error, canApprove, showBranch } = props;
  return (
    <div className="card" style={{ overflow: "visible" }}>
      <div className="card-header">
        <span className="card-title">
          <i className="ti ti-clipboard-list" /> Submissions ({props.matching})
        </span>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: "0 20px 16px" }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
          <button type="button" className="btn-link" style={{ marginLeft: "auto" }} onClick={props.onRetry}>Try again</button>
        </div>
      )}

      {isLoading && rows.length === 0 ? <Skeleton /> : rows.length === 0 ? (
        error ? null : <EmptyState hasFilters={props.hasFilters} onClearFilters={props.onClearFilters} />
      ) : (
        <div className="table-wrap" style={{ opacity: isLoading ? 0.6 : 1 }}>
          <table className="data-table" style={{ minWidth: 560 }}>
            <thead>
              <tr>
                <th>Name</th><th className="col-hide-sm">Designation</th>
                {showBranch && <th className="col-hide-md">Company Code</th>}
                <th className="col-hide-md">Joined</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const meta = statusMeta(row.onboarding_status);
                return (
                  <tr key={row.id}>
                    <td>
                      <div className="cand-person">
                        <div className="user-avatar" style={{ width: 34, height: 34, fontSize: 12, flexShrink: 0 }}>{initials(row.full_name)}</div>
                        <div className="cand-person-text">
                          <strong>{row.full_name}</strong>
                          <span>{row.email}</span>
                        </div>
                      </div>
                    </td>
                    <td className="col-hide-sm">{row.designation || "—"}</td>
                    {showBranch && <td className="col-hide-md">{row.branch || "—"}</td>}
                    <td className="col-hide-md">{fmtDate(row.date_joined)}</td>
                    <td><span className={`badge ${meta.badge}`} style={{ whiteSpace: "nowrap" }}><i className={`ti ${meta.icon}`} /> {meta.label}</span></td>
                    <td><ActionCell row={row} canApprove={canApprove} onReview={props.onReview} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {props.totalPages > 1 && (
        <div className="cand-pager">
          <span>{rangeLabel(props.page, props.pageSize, rows.length, props.matching)}</span>
          <div className="cand-pager-buttons">
            <button type="button" className="btn btn-ghost btn-sm" disabled={props.page <= 1 || isLoading} onClick={() => props.onPageChange(props.page - 1)}>
              <i className="ti ti-chevron-left" /> Prev
            </button>
            <span className="cand-pager-page">Page {props.page} of {props.totalPages}</span>
            <button type="button" className="btn btn-ghost btn-sm" disabled={props.page >= props.totalPages || isLoading} onClick={() => props.onPageChange(props.page + 1)}>
              Next <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
