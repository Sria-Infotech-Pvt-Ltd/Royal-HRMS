"use client";

import type { Ref } from "react";
import { FACE_STATE_META, emptyListMessage, faceStateOf, personInitials, pickerRange } from "@/lib/faceRegistrationStatus";
import type { FaceRegistrationEmployee, FaceRosterFilter } from "@/types/faceRegistration";
import { useT } from "@/hooks/useI18n";

interface EmployeePickerPanelProps {
  search:      string
  onSearch:    (text: string) => void
  employees:   FaceRegistrationEmployee[]
  total:       number
  page:        number
  pageSize:    number
  totalPages:  number
  onPage:      (page: number) => void
  isLoading:   boolean
  error:       string | null
  selectedId:  string | null
  /** The Face ID filter that is on, so an empty list can say why. */
  filter:      FaceRosterFilter
  /** Lets the page move the cursor into the search box (step 1 of the guide). */
  searchRef?:  Ref<HTMLInputElement>
  onSelect:    (employee: FaceRegistrationEmployee) => void
}

/** Search box, the employee list (one page at a time) and page controls. */
export default function EmployeePickerPanel(props: EmployeePickerPanelProps) {
  const { search, employees, total, page, pageSize, totalPages, isLoading, error, selectedId, filter, searchRef } = props;
  const t = useT();
  const range = pickerRange(page, pageSize, employees.length, total);
  return (
    <div className="card fid-picker">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-users" /> {t("Employees")}</span>
        {total > 0 && <span className="fid-count">{total.toLocaleString()}</span>}
      </div>

      <div className="fid-picker-body">
        <div className="cand-search">
          <i className="ti ti-search" aria-hidden="true" />
          <input
            type="search" className="field-input" placeholder={t("Search by name, email or ID")}
            aria-label={t("Search employees by name, email or ID")} value={search} maxLength={100} ref={searchRef}
            onChange={event => props.onSearch(event.target.value)} suppressHydrationWarning
          />
          {search && (
            <button type="button" className="cand-search-clear" aria-label={t("Clear search")} onClick={() => props.onSearch("")}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>

        {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

        <ul className={`fid-list${isLoading && employees.length > 0 ? " is-loading" : ""}`} aria-label={t("Employees")}>
          {isLoading && employees.length === 0 && [0, 1, 2, 3, 4].map(row => (
            <li key={row} className="fid-skel"><span className="cand-skeleton-dot" /><span className="cand-skeleton-bar" /></li>
          ))}
          {!isLoading && employees.length === 0 && (
            <li className="fid-none">
              <i className={`ti ${filter === "incomplete" && !search ? "ti-circle-check" : "ti-user-search"}`} />
              <strong>{t(emptyListMessage(filter, search.trim() !== "").title)}</strong>
              <span>{t(emptyListMessage(filter, search.trim() !== "").text)}</span>
            </li>
          )}
          {employees.map(employee => {
            const isSelected = employee.uuid === selectedId;
            const meta = FACE_STATE_META[faceStateOf(employee.face_status)];
            return (
              <li key={employee.uuid}>
                <button type="button" className={`fid-row${isSelected ? " is-selected" : ""}`} aria-pressed={isSelected} onClick={() => props.onSelect(employee)}>
                  <span className="fid-avatar" aria-hidden="true">{personInitials(employee.full_name)}</span>
                  <span className="fid-row-text">
                    <strong>{employee.full_name}</strong>
                    <span>{[employee.employee_id, employee.designation, employee.branch].filter(Boolean).join(" · ")}</span>
                  </span>
                  <span className={`badge ${meta.badge} fid-row-badge`}><i className={`ti ${meta.icon}`} /> {t(meta.label)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {totalPages > 1 && (
        <div className="cand-pager">
          <span>{range}</span>
          <div className="cand-pager-buttons">
            <button type="button" className="btn btn-ghost btn-sm" aria-label={t("Previous page")} disabled={page <= 1 || isLoading} onClick={() => props.onPage(page - 1)}>
              <i className="ti ti-chevron-left" />
            </button>
            <span className="cand-pager-page">{page} / {totalPages}</span>
            <button type="button" className="btn btn-ghost btn-sm" aria-label={t("Next page")} disabled={page >= totalPages || isLoading} onClick={() => props.onPage(page + 1)}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
