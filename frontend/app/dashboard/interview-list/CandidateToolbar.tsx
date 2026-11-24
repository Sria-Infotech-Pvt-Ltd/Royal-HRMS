"use client";

import type { Branch, CandidateStatus } from "./_data";
import type { StatusFilter } from "./_filters";
import { useT } from "@/hooks/useI18n";

interface CandidateToolbarProps {
  search:          string
  onSearch:        (text: string) => void
  branches:        Branch[]
  branchFilter:    number | ""
  onBranch:        (branch: number | "") => void
  /** Only some people may switch company code; everyone else is locked to their own. */
  canChooseBranch: boolean
  lockedBranch:    string
  statusFilter:    StatusFilter
  statusChoices:   { value: CandidateStatus; label: string }[]
  onStatus:        (status: StatusFilter) => void
  hasFilters:      boolean
  onClear:         () => void
}

/** One row of filters (search, company code, hiring stage) and, when something is filtered, removable chips showing what. */
function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  const t = useT();
  return (
    <span className="cand-chip">
      {label}
      <button type="button" aria-label={t("Remove filter {label}", { label })} onClick={onRemove}><i className="ti ti-x" aria-hidden="true" /></button>
    </span>
  );
}

export default function CandidateToolbar(props: CandidateToolbarProps) {
  const t = useT();
  const { search, branchFilter, canChooseBranch, lockedBranch, statusFilter, statusChoices, hasFilters } = props

  const statusLabel = statusChoices.find(choice => choice.value === statusFilter)?.label ?? statusFilter
  const activeBranch = props.branches.find(branch => branch.id === branchFilter)
  const branchLabel = activeBranch ? activeBranch.branch_name : t("Company code")

  return (
    <div className="card cand-toolbar">
      <div className="cand-toolbar-row">
        <div className="cand-search">
          <i className="ti ti-search" aria-hidden="true" />
          <input
            type="search"
            className="field-input"
            placeholder={t("Search by name, email or position")}
            aria-label={t("Search candidates")}
            value={search}
            onChange={event => props.onSearch(event.target.value)}
            suppressHydrationWarning
          />
          {search && (
            <button type="button" className="cand-search-clear" aria-label={t("Clear search")} onClick={() => props.onSearch("")}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>

        {canChooseBranch ? (
          <label className="cand-select">
            <i className="ti ti-building" aria-hidden="true" />
            <span className="sr-only">{t("Company code")}</span>
            <select
              className="field-input field-select"
              value={branchFilter}
              onChange={event => props.onBranch(event.target.value ? Number(event.target.value) : "")}
              suppressHydrationWarning
            >
              <option value="">{t("All Company Codes")}</option>
              {props.branches.map(branch => (
                <option key={branch.id} value={branch.id}>{branch.branch_name} ({branch.branch_code})</option>
              ))}
            </select>
          </label>
        ) : (
          <span className="cand-lock" title={t("Scoped to your Company Code")}>
            <i className="ti ti-lock" aria-hidden="true" /> {lockedBranch || "—"}
          </span>
        )}

        <label className="cand-select">
          <i className="ti ti-filter" aria-hidden="true" />
          <span className="sr-only">{t("Hiring stage")}</span>
          <select
            className="field-input field-select"
            value={statusFilter}
            onChange={event => props.onStatus(event.target.value as StatusFilter)}
            suppressHydrationWarning
          >
            <option value="">{t("All stages")}</option>
            {statusChoices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
          </select>
        </label>
      </div>

      {hasFilters && (
        <div className="cand-chips" aria-label={t("Active filters")}>
          <span className="cand-chips-label">{t("Filtered by")}</span>
          {search.trim() && <Chip label={`“${search.trim()}”`} onRemove={() => props.onSearch("")} />}
          {statusFilter && <Chip label={statusLabel} onRemove={() => props.onStatus("")} />}
          {canChooseBranch && branchFilter !== "" && <Chip label={branchLabel} onRemove={() => props.onBranch("")} />}
          <button type="button" className="btn-link" onClick={props.onClear}>{t("Clear all")}</button>
        </div>
      )}
    </div>
  );
}
