"use client";

import { useRouter } from "next/navigation";
import ProjectSyncStatusCard from "@/components/work-status/ProjectSyncStatusCard";

export default function ProjectSyncSettingsPage() {
  const router = useRouter();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Project Budgeting sync</div>
          <div className="page-sub">
            Employees&apos; projects are managed in Project Budgeting and shown in AIRA. Problems and employees AIRA could not match appear here.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" type="button" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back to Settings
          </button>
        </div>
      </div>

      <ProjectSyncStatusCard />
    </>
  );
}
