"use client";

import { useRouter } from "next/navigation";
import { useT } from "@/hooks/useI18n";
import ProjectSyncStatusCard from "@/components/work-status/ProjectSyncStatusCard";

export default function ProjectSyncSettingsPage() {
  const router = useRouter();
  const t = useT();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Project Budgeting sync")}</div>
          <div className="page-sub">
            {t("Employees' projects are managed in Project Budgeting and shown in AIRA. Problems and employees AIRA could not match appear here.")}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" type="button" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> {t("Back to Settings")}
          </button>
        </div>
      </div>

      <ProjectSyncStatusCard />
    </>
  );
}
