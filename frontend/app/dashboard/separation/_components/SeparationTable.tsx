"use client";

import type { SeparationRequest } from "@/types/separation";
import { useT } from "@/hooks/useI18n";
import { fmtDate, statusBadgeClass } from "../_workflow";
import { lastDayCountdown } from "../_view";
import { SeparationStyles } from "./separationStyles";

function initialsOf(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("") || "?";
}

interface Props {
  requests: SeparationRequest[];
  onView:   (r: SeparationRequest) => void;
  onEdit:   (r: SeparationRequest) => void;
  onCancel: (r: SeparationRequest) => void;
  onReject: (r: SeparationRequest) => void;
  /** Empty-state shortcut; omitted when the list is empty only because of a filter. */
  onRequest?: () => void;
  isFiltered?: boolean;
}

export default function SeparationTable({ requests, onView, onEdit, onCancel, onReject, onRequest, isFiltered = false }: Props) {
  const t = useT();
  if (requests.length === 0) {
    return (
      <div className="sp-empty">
        <SeparationStyles />
        <span className="sp-empty-icon"><i className="ti ti-logout" /></span>
        <b>{isFiltered ? t("No separation requests match your filters.") : t("No separation requests yet.")}</b>
        <p>{isFiltered ? t("Try another status or clear the search.") : t("When someone resigns or an exit is raised, it shows up here with its approval progress.")}</p>
        {!isFiltered && onRequest && <button type="button" className="btn btn-filled btn-sm" style={{ marginTop: 14 }} onClick={onRequest}><i className="ti ti-plus" /> {t("Request Separation")}</button>}
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <SeparationStyles />
      <table className="sp-table">
        <thead>
          <tr>
            <th>{t("Request")}</th>
            <th>{t("Employee")}</th>
            <th>{t("Employee Code")}</th>
            <th>{t("Separation Type")}</th>
            <th>{t("Reason")}</th>
            <th>{t("Request Date")}</th>
            <th>{t("Proposed Last Working Day")}</th>
            <th>{t("Notice Period")}</th>
            <th>{t("Status")}</th>
            <th>{t("Reporting Manager")}</th>
            <th style={{ textAlign: "right" }}>{t("Actions")}</th>
          </tr>
        </thead>
        <tbody>
          {requests.map(r => {
            const countdown = lastDayCountdown(r.proposed_last_working_day);
            return (
            <tr key={r.id} onClick={() => onView(r)} style={{ cursor: "pointer" }} className={r.can_approve ? "needs-me" : ""}>
              <td style={{ color: "var(--on-variant)" }}>
                {r.request_ref}
                {r.can_approve && <span className="badge badge-error" style={{ marginLeft: 6, fontSize: 10 }}>{t("Action needed")}</span>}
              </td>
              <td>
                <div className="sp-person">
                  <span className="sp-avatar" aria-hidden="true">{initialsOf(r.employee_name)}</span>
                  <span style={{ fontWeight: 600 }}>{r.employee_name}</span>
                </div>
              </td>
              <td style={{ color: "var(--on-variant)" }}>{r.employee_code}</td>
              <td><span className="sp-type">{r.separation_type_display}</span></td>
              <td>{r.reason_display}</td>
              <td>{fmtDate(r.request_date)}</td>
              <td>
                {fmtDate(r.proposed_last_working_day)}
                {countdown && <div><span className={`sp-left is-${countdown.tone}`}><i className="ti ti-calendar-time" /> {countdown.label}</span></div>}
              </td>
              <td>{t("{count} days", { count: r.notice_period_days })}</td>
              <td>
                <span className={`badge ${statusBadgeClass(r.status)}`}>{r.status_display}</span>
                {r.is_stale && <span className="badge badge-warn" style={{ marginLeft: 6 }} title={t("The last working day has passed but no decision was made")}>{t("Last day passed")}</span>}
              </td>
              <td style={{ color: "var(--on-variant)" }}>{r.reporting_manager?.name ?? t("Not assigned")}</td>
              <td onClick={e => e.stopPropagation()}>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => onView(r)} title={t("View")} suppressHydrationWarning aria-label={t("View")}>
                    <i className="ti ti-eye" />
                  </button>
                  {r.can_edit && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onEdit(r)} title={t("Edit")} suppressHydrationWarning aria-label={t("Edit")}>
                      <i className="ti ti-edit" />
                    </button>
                  )}
                  {r.can_cancel && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onCancel(r)} title={t("Cancel Request")} suppressHydrationWarning aria-label={t("Cancel Request")}>
                      <i className="ti ti-ban" />
                    </button>
                  )}
                  {r.can_delete && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onReject(r)} title={t("Reject")} style={{ color: "var(--error)" }} suppressHydrationWarning aria-label={t("Reject")}>
                      <i className="ti ti-x" />
                    </button>
                  )}
                </div>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
