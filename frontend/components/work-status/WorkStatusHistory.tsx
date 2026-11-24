"use client";

import type { WorkStatusHistoryPage } from "@/types/workStatus";
import { useT } from "@/hooks/useI18n";
import { STATUS_BADGE, changeLabel, endLabel, fmtDate, statusLabel } from "./workStatusFormat";

interface Props {
  history:      WorkStatusHistoryPage;
  onPageChange: (page: number) => void;
}

export default function WorkStatusHistory({ history, onPageChange }: Props) {
  const t = useT();
  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%", fontSize: 12 }}>
          <thead>
            <tr>
              <th>{t("Project")}</th><th>{t("Role")}</th><th>{t("Allocation")}</th><th>{t("Start")}</th><th>{t("End")}</th><th>{t("Status")}</th><th>{t("Last change")}</th>
            </tr>
          </thead>
          <tbody>
            {history.results.map(assignment => (
              <tr key={assignment.assignment_id}>
                <td>
                  <div style={{ fontWeight: 500 }}>{assignment.project_name}</div>
                  <div style={{ color: "var(--on-variant)" }}>
                    {assignment.project_code || t("ID {id}", { id: assignment.project_id })} · {assignment.milestone_name || t("Whole project")}
                  </div>
                </td>
                <td>{assignment.role || "—"}</td>
                <td>{assignment.allocation_percent ? `${assignment.allocation_percent}%` : "—"}</td>
                <td>{fmtDate(assignment.start_date)}</td>
                <td>{endLabel(assignment)}</td>
                <td>
                  <span className={STATUS_BADGE[assignment.assignment_status] ?? "badge badge-neutral"} style={{ fontSize: 10 }}>
                    {statusLabel(assignment)}
                  </span>
                </td>
                <td style={{ color: "var(--on-variant)" }}>{changeLabel(assignment.last_change)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {history.total_pages > 1 && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, padding: "8px 0" }}>
          <button className="btn btn-outline btn-sm" disabled={history.page <= 1} onClick={() => onPageChange(history.page - 1)}><i className="ti ti-chevron-left" /> {t("Previous")}</button>
          <span style={{ fontSize: 12 }}>{t("Page {page} of {total}", { page: history.page, total: history.total_pages })}</span>
          <button className="btn btn-outline btn-sm" disabled={history.page >= history.total_pages} onClick={() => onPageChange(history.page + 1)}>{t("Next")} <i className="ti ti-chevron-right" /></button>
        </div>
      )}
    </>
  );
}
