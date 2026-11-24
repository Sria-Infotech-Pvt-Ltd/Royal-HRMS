"use client";

import { useState } from "react";
import { useProjectSyncStatus } from "@/hooks/useWorkStatus";
import type { ProjectSyncStatus } from "@/types/workStatus";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import { fmtDateTime } from "./workStatusFormat";
import { changeSummary, groupLogs, plainMessage, whatHappened } from "./projectSyncFormat";

const RESULT_LABEL: Record<string, { text: string; badge: string }> = {
  success:   { text: "Synced",    badge: "badge badge-success" },
  failed:    { text: "Failed",    badge: "badge badge-error" },
  unmatched: { text: "Employee not found", badge: "badge badge-warn" },
};

interface Tile { label: string; value: string; note: string; isProblem?: boolean }

function tilesFor(data: ProjectSyncStatus): Tile[] {
  return [
    { label: tr("Last synced"), value: data.last_synced_at ? fmtDateTime(data.last_synced_at) : tr("Never"), note: tr("last successful update") },
    { label: tr("Failed attempts"), value: String(data.failed_last_24h), note: tr("in the last 24 hours"), isProblem: data.failed_last_24h > 0 },
    { label: tr("Active assignments"), value: String(data.open_assignments), note: tr("employees currently on a project") },
    { label: tr("Regular check"), value: data.is_pull_configured ? tr("On") : tr("Off"), note: data.is_pull_configured ? tr("AIRA asks Project Budgeting every 30 minutes") : tr("only updates sent by Project Budgeting") },
  ];
}

// One sentence on top: is it working right now, and if not, why. Only meaningful on the newest page of the log.
function StatusBanner({ data }: { data: ProjectSyncStatus }) {
  const t = useT();
  const latest = data.logs.page === 1 ? data.logs.results[0] : undefined;
  if (!latest) return null;

  if (latest.status === "failed") {
    return (
      <div className="alert alert-error" style={{ marginBottom: 16 }}>
        <i className="ti ti-plug-connected-x" />
        <div>
          <b>{t("Project details are not updating right now.")}</b>
          <div style={{ marginTop: 2 }}>{plainMessage(latest.message) || t("The last sync failed.")}</div>
          <div style={{ marginTop: 2, opacity: 0.8 }}>
            {t("Last successful update: {when}. Project details already in AIRA are safe and unchanged.", { when: data.last_synced_at ? fmtDateTime(data.last_synced_at) : t("none yet") })}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="alert alert-success" style={{ marginBottom: 16 }}>
      <i className="ti ti-circle-check" />
      <div><b>{t("Working normally.")}</b> {t("Last update {when}.", { when: fmtDateTime(latest.at) })}</div>
    </div>
  );
}

function Pager({ logs, onPage }: { logs: ProjectSyncStatus["logs"]; onPage: (page: number) => void }) {
  const t = useT();
  if (logs.total_pages <= 1) return null;
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, padding: "12px 0 0" }}>
      <button className="btn btn-outline btn-sm" disabled={logs.page <= 1} onClick={() => onPage(logs.page - 1)}><i className="ti ti-chevron-left" /> {t("Previous")}</button>
      <span style={{ fontSize: 12 }}>{t("Page {page} of {total}", { page: logs.page, total: logs.total_pages })}</span>
      <button className="btn btn-outline btn-sm" disabled={logs.page >= logs.total_pages} onClick={() => onPage(logs.page + 1)}>{t("Next")} <i className="ti ti-chevron-right" /></button>
    </div>
  );
}

// Admin view of the Project Budgeting sync: is it working, what failed, which employee IDs couldn't be matched, and the log.
export default function ProjectSyncStatusCard() {
  const t = useT();
  const [page, setPage] = useState(1);
  const { data, loading, error } = useProjectSyncStatus(page);

  if (loading && !data) return <div style={{ fontSize: 13 }}><i className="ti ti-loader-2 spin" /> {t("Loading…")}</div>;
  if (error || !data) return <div className="alert alert-error">{error ?? t("Could not load sync status.")}</div>;

  const groups = groupLogs(data.logs.results);

  return (
    <div>
      <StatusBanner data={data} />

      <div className="stats-grid">
        {tilesFor(data).map(tile => (
          <div className="stat-card" key={tile.label}>
            <div className="stat-label">{tile.label}</div>
            <div className="stat-value" style={{ fontSize: 20, color: tile.isProblem ? "var(--error)" : undefined }}>{tile.value}</div>
            <div className="stat-sub">{tile.note}</div>
          </div>
        ))}
      </div>

      {data.unmatched_employee_ids.length > 0 && (
        <div className="alert alert-warn" style={{ marginBottom: 16 }}>
          <i className="ti ti-user-question" />
          <div>
            {t("Project Budgeting sent assignments for employee IDs that don't exist in AIRA:")}{" "}
            <b>{data.unmatched_employee_ids.join(", ")}</b>. {t("Fix the ID in Project Budgeting, or add the employee here.")}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-history" /> {t("Recent activity")}</div>
        </div>
        <div className="card-body">
          {groups.length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{t("Nothing has synced yet.")}</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ width: "100%", fontSize: 13 }}>
              <thead><tr><th>{t("When")}</th><th>{t("What happened")}</th><th>{t("Result")}</th><th>{t("Details")}</th></tr></thead>
              <tbody>
                {groups.map(({ first, latest, count }) => (
                  <tr key={`${latest.at}-${latest.employee_id}-${latest.source}`}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {fmtDateTime(latest.at)}
                      {count > 1 && <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{t("from {when}", { when: fmtDateTime(first.at) })}</div>}
                    </td>
                    <td>{whatHappened(latest)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <span className={(RESULT_LABEL[latest.status] ?? RESULT_LABEL.success).badge} style={{ fontSize: 10 }}>
                        {t((RESULT_LABEL[latest.status] ?? RESULT_LABEL.success).text)}
                      </span>
                      {count > 1 && <span style={{ marginLeft: 6, fontSize: 11, color: "var(--on-variant)" }}>{t("{count} times", { count })}</span>}
                    </td>
                    <td style={{ color: "var(--on-variant)", maxWidth: 440 }} title={latest.message || undefined}>
                      <div style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                        {plainMessage(latest.message) || changeSummary(latest)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
          <Pager logs={data.logs} onPage={setPage} />
        </div>
      </div>
    </div>
  );
}
