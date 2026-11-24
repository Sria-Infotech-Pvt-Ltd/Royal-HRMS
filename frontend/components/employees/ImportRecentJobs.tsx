"use client";

import { useT } from "@/hooks/useI18n";
import { JOB_STATUS_LABEL } from "@/lib/employeeImport";
import type { ImportJobProgress } from "@/types/employeeImport";

interface Props {
  jobs: ImportJobProgress[];
  onOpen: (jobId: string) => void;
}

const MAX_SHOWN = 5;

/** The last few imports, so a finished or running one can be reopened after the window was closed. */
export default function ImportRecentJobs({ jobs, onOpen }: Props) {
  const t = useT();
  if (jobs.length === 0) return null;
  return (
    <div data-testid="recent-imports" style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 10, marginTop: 14 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>{t("Recent imports")}</div>
      {jobs.slice(0, MAX_SHOWN).map(job => (
        <div key={job.job_id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, padding: "3px 0" }}>
          <span style={{ flex: 1 }}>
            {job.file_name || t("Import")} · {t(JOB_STATUS_LABEL[job.status])} · {t("{count} created", { count: job.created })}
            {job.failed_rows > 0 ? `, ${t("{count} failed", { count: job.failed_rows })}` : ""} · {t("emails {count} sent", { count: job.invitations.sent })}
            {job.invitations.failed > 0 ? `, ${t("{count} failed", { count: job.invitations.failed })}` : ""}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={() => onOpen(job.job_id)} suppressHydrationWarning>{t("View")}</button>
        </div>
      ))}
    </div>
  );
}
