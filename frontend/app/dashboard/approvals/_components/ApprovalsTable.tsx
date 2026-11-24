"use client";

import { useEffect, useMemo, useState } from "react";
import { useT } from "@/hooks/useI18n";
import { ApprovalItem, fmtSubmitted, initials, toSortableTime } from "../_data";
import { TypeBadge, StatusChip } from "./Badges";

type SortKey = "employeeName" | "submittedAt" | "status";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 10;
const AGING_AFTER_DAYS = 3;
const LATE_AFTER_DAYS = 7;
const MS_PER_DAY = 86_400_000;

/** How long a pending request has been waiting: whole days, and a tone (fresh / aging / late) for the colour. */
function waitingFor(item: ApprovalItem): { days: number; tone: "fresh" | "aging" | "late" } | null {
  if (item.displayStatus !== "pending") return null;
  const submitted = toSortableTime(item.submittedAt);
  if (!submitted) return null;
  const days = Math.max(0, Math.floor((Date.now() - submitted) / MS_PER_DAY));
  return { days, tone: days >= LATE_AFTER_DAYS ? "late" : days >= AGING_AFTER_DAYS ? "aging" : "fresh" };
}

interface Props {
  items:      ApprovalItem[]; // filtered, not yet sorted/paginated
  loading:    boolean;
  resetKey:   string;
  selected:   Set<string>;
  onToggleSelect:    (key: string) => void;
  onToggleSelectMany: (keys: string[], select: boolean) => void;
  onView:     (item: ApprovalItem) => void;
  onApprove:  (item: ApprovalItem) => void;
  onReject:   (item: ApprovalItem) => void;
  onBulkApprove: () => void;
  onBulkReject:  () => void;
  bulkBusy:   boolean;
  /** Empty-state shortcut: drop the "pending only" filter to look at past decisions. */
  onShowAll?: () => void;
  onRefresh?: () => void;
}

function SortHeader({
  label, sortKey, active, dir, onClick,
}: { label: string; sortKey: SortKey; active: boolean; dir: SortDir; onClick: (k: SortKey) => void }) {
  const t = useT();
  return (
    <th>
      <span className="ta-th-sort" onClick={() => onClick(sortKey)}>
        {t(label)}
        <i className={`ti ${active ? (dir === "asc" ? "ti-arrow-up" : "ti-arrow-down") : "ti-arrows-sort"}`} />
      </span>
    </th>
  );
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i}>
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j}><div className="ta-skel" style={{ height: 14, width: j === 0 ? "70%" : "50%" }} /></td>
          ))}
        </tr>
      ))}
    </>
  );
}

export default function ApprovalsTable({
  items, loading, resetKey, selected,
  onToggleSelect, onToggleSelectMany, onView, onApprove, onReject,
  onBulkApprove, onBulkReject, bulkBusy, onShowAll, onRefresh,
}: Props) {
  const t = useT();
  const [sortKey, setSortKey] = useState<SortKey>("submittedAt");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page,    setPage]    = useState(1);

  useEffect(() => { setPage(1); }, [resetKey]);

  function handleSort(key: SortKey) {
    if (key === sortKey) { setSortDir(d => (d === "asc" ? "desc" : "asc")); }
    else { setSortKey(key); setSortDir("asc"); }
  }

  const sorted = useMemo(() => {
    const arr = [...items];
    arr.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "employeeName") cmp = a.employeeName.localeCompare(b.employeeName);
      else if (sortKey === "status")  cmp = a.displayStatus.localeCompare(b.displayStatus);
      else                             cmp = toSortableTime(a.submittedAt) - toSortableTime(b.submittedAt);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [items, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pageWindowSize = Math.min(5, totalPages);
  const pageWindowStart = Math.max(1, Math.min(page - 2, totalPages - pageWindowSize + 1));

  const pageKeys = pageItems.map(i => i.key);
  const allPageSelected = pageKeys.length > 0 && pageKeys.every(k => selected.has(k));
  const allFilteredSelected = sorted.length > 0 && sorted.every(i => selected.has(i.key));
  const selectedCount = selected.size;
  const colCount = 8; // checkbox, employee, employee id, type, details, submitted, status, actions

  const isEmpty = !loading && items.length === 0;

  return (
    <>
      {selectedCount > 0 && (
        <div className="ta-bulk-bar">
          <span className="ta-bulk-count">{t("{count} selected", { count: selectedCount })}</span>
          {!allFilteredSelected && (
            <button
              className="ta-page-btn"
              onClick={() => onToggleSelectMany(sorted.map(i => i.key), true)}
              suppressHydrationWarning
            >
              {t("Select all {count}", { count: sorted.length })}
            </button>
          )}
          <button className="ta-bulk-btn ta-bulk-approve" onClick={onBulkApprove} disabled={bulkBusy} suppressHydrationWarning>
            <i className="ti ti-check" /> {t("Approve Selected")}
          </button>
          <button className="ta-bulk-btn ta-bulk-reject" onClick={onBulkReject} disabled={bulkBusy} suppressHydrationWarning>
            <i className="ti ti-x" /> {t("Reject Selected")}
          </button>
          <button className="ta-bulk-clear" onClick={() => onToggleSelectMany(sorted.map(i => i.key), false)} suppressHydrationWarning>
            {t("Clear")}
          </button>
        </div>
      )}

      <div className="ta-table-card">
        {isEmpty ? (
          <div className="ta-empty">
            <div className="ta-empty-icon"><i className="ti ti-check" /></div>
            <div className="ta-empty-title">{t("You’re all caught up!")}</div>
            <div className="ta-empty-sub">{t("No approval requests are waiting for your action.")}</div>
            <div className="tv-empty-actions">
              {onRefresh && <button type="button" className="btn btn-outline btn-sm" onClick={onRefresh}><i className="ti ti-refresh" /> {t("Check again")}</button>}
              {onShowAll && <button type="button" className="btn btn-ghost btn-sm" onClick={onShowAll}><i className="ti ti-history" /> {t("See past decisions")}</button>}
            </div>
            <div className="tv-empty-tips">
              <span><i className="ti ti-bell" />{t("New requests show up here and in your notifications.")}</span>
              <span><i className="ti ti-checks" />{t("Tick several rows to approve or reject in one go.")}</span>
            </div>
          </div>
        ) : (
          <>
            <div className="ta-table-scroll">
              <table className="ta-table">
                <thead>
                  <tr>
                    <th style={{ width: 36 }}>
                      <input
                        type="checkbox"
                        className="ta-checkbox"
                        checked={allPageSelected}
                        onChange={e => onToggleSelectMany(pageKeys, e.target.checked)}
                        suppressHydrationWarning
                      />
                    </th>
                    <SortHeader label="Employee" sortKey="employeeName" active={sortKey === "employeeName"} dir={sortDir} onClick={handleSort} />
                    <th>{t("Employee ID")}</th>
                    <th>{t("Request Type")}</th>
                    <th>{t("Request Details")}</th>
                    <SortHeader label="Submitted Date" sortKey="submittedAt" active={sortKey === "submittedAt"} dir={sortDir} onClick={handleSort} />
                    <SortHeader label="Status" sortKey="status" active={sortKey === "status"} dir={sortDir} onClick={handleSort} />
                    <th style={{ textAlign: "right" }}>{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && items.length === 0 ? (
                    <SkeletonRows cols={colCount} />
                  ) : (
                    pageItems.map(item => {
                      const waiting = waitingFor(item);
                      const rowClasses = [selected.has(item.key) ? "selected" : "", waiting?.tone === "late" ? "tv-late-row" : "", waiting?.tone === "aging" ? "tv-aging-row" : ""].filter(Boolean).join(" ");
                      return (
                      <tr key={item.key} className={rowClasses} style={{ cursor: "pointer" }} onClick={() => onView(item)}>
                        <td onClick={e => e.stopPropagation()}>
                          {item.kind !== "separation" && (
                            <input
                              type="checkbox"
                              className="ta-checkbox"
                              checked={selected.has(item.key)}
                              onChange={() => onToggleSelect(item.key)}
                              suppressHydrationWarning
                            />
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div className="ta-emp-avatar">{initials(item.employeeName)}</div>
                            <div>
                              <div className="ta-emp-name">{item.employeeName}</div>
                              {item.department && <div className="ta-emp-sub">{item.department}</div>}
                            </div>
                          </div>
                        </td>
                        <td className="ta-mono">{item.employeeCode}</td>
                        <td><TypeBadge kind={item.kind} /></td>
                        <td>
                          <div className="ta-detail-primary">{item.detailPrimary}</div>
                          {item.detailSecondary && <div className="ta-detail-secondary">{item.detailSecondary}</div>}
                          {item.detailTertiary && <div className="ta-detail-secondary">{item.detailTertiary}</div>}
                        </td>
                        <td>
                          <div className="ta-mono">{fmtSubmitted(item.submittedAt)}</div>
                          {waiting && (
                            <span className={`tv-wait is-${waiting.tone}`} title={t("How long this request has been waiting")}>
                              <i className="ti ti-hourglass" /> {waiting.days === 0 ? t("Today") : waiting.days === 1 ? t("{count} day", { count: waiting.days }) : t("{count} days", { count: waiting.days })}
                            </span>
                          )}
                        </td>
                        <td><StatusChip status={item.displayStatus} /></td>
                        <td onClick={e => e.stopPropagation()}>
                          <div className="ta-actions" style={{ justifyContent: "flex-end" }}>
                            <button className="ta-icon-btn view" title={t("View")} onClick={() => onView(item)} suppressHydrationWarning aria-label={t("View")}>
                              <i className="ti ti-eye" />
                            </button>
                            <button
                              className="ta-icon-btn approve"
                              title={t("Approve")}
                              disabled={!item.canAction}
                              onClick={() => onApprove(item)}
                              suppressHydrationWarning
                             aria-label={t("Approve")}>
                              <i className="ti ti-check" />
                            </button>
                            <button
                              className="ta-icon-btn reject"
                              title={t("Reject")}
                              disabled={!item.canAction}
                              onClick={() => onReject(item)}
                              suppressHydrationWarning
                             aria-label={t("Reject")}>
                              <i className="ti ti-x" />
                            </button>
                          </div>
                        </td>
                      </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="ta-pagination">
                <span className="ta-pagination-info">
                  {t("Showing {from}–{to} of {total}", { from: (page - 1) * PAGE_SIZE + 1, to: Math.min(page * PAGE_SIZE, sorted.length), total: sorted.length })}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <button className="ta-page-btn" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} suppressHydrationWarning>
                    <i className="ti ti-chevron-left" /> {t("Prev")}
                  </button>
                  {Array.from({ length: pageWindowSize }, (_, i) => pageWindowStart + i).map(n => (
                    <button
                      key={n}
                      className={`ta-page-num ${page === n ? "active" : ""}`}
                      onClick={() => setPage(n)}
                      suppressHydrationWarning
                    >
                      {n}
                    </button>
                  ))}
                  <button className="ta-page-btn" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} suppressHydrationWarning>
                    {t("Next")} <i className="ti ti-chevron-right" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
