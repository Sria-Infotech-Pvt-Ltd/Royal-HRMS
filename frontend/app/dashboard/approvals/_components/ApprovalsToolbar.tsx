"use client";

import { ApprovalKind, DisplayStatus, STATUS_FILTERS, TYPE_BADGE } from "../_data";
import DateInput from "@/components/shared/DateInput";

interface Props {
  search:        string;
  onSearch:      (v: string) => void;
  status:        "all" | DisplayStatus;
  onStatus:      (v: "all" | DisplayStatus) => void;
  showTypeFilter: boolean;
  type:          "all" | ApprovalKind;
  onType:        (v: "all" | ApprovalKind) => void;
  dateFrom:      string;
  onDateFrom:    (v: string) => void;
  dateTo:        string;
  onDateTo:      (v: string) => void;
  onRefresh:     () => void;
  refreshing:    boolean;
}

export default function ApprovalsToolbar({
  search, onSearch, status, onStatus, showTypeFilter, type, onType,
  dateFrom, onDateFrom, dateTo, onDateTo, onRefresh, refreshing,
}: Props) {
  return (
    <div className="ta-toolbar">
      <div className="ta-search-box">
        <i className="ti ti-search" />
        <input
          type="text"
          placeholder="Search employee name or ID…"
          value={search}
          onChange={e => onSearch(e.target.value)}
          suppressHydrationWarning
        />
      </div>

      <select
        className="ta-filter-select"
        value={status}
        onChange={e => onStatus(e.target.value as "all" | DisplayStatus)}
        suppressHydrationWarning
      >
        {STATUS_FILTERS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
      </select>

      {showTypeFilter && (
        <select
          className="ta-filter-select"
          value={type}
          onChange={e => onType(e.target.value as "all" | ApprovalKind)}
          suppressHydrationWarning
        >
          <option value="all">All Types</option>
          {(Object.keys(TYPE_BADGE) as ApprovalKind[]).map(k => (
            <option key={k} value={k}>{TYPE_BADGE[k].label}</option>
          ))}
        </select>
      )}

      <DateInput className="ta-date-input" value={dateFrom} onChange={isoDate => onDateFrom(isoDate)} title="Submitted from" />
      <span style={{ fontSize: 12, color: "var(--ta-text-faint)" }}>to</span>
      <DateInput className="ta-date-input" value={dateTo} onChange={isoDate => onDateTo(isoDate)} title="Submitted to" />

      <button className="ta-refresh-btn" onClick={onRefresh} disabled={refreshing} suppressHydrationWarning>
        <i className={`ti ti-refresh ${refreshing ? "spin" : ""}`} />
        Refresh
      </button>
    </div>
  );
}
