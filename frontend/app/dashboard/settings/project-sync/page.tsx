"use client";

import ProjectSyncStatusCard from "@/components/work-status/ProjectSyncStatusCard";

export default function ProjectSyncSettingsPage() {
  return (
    <div>
      <h2 style={{ margin: "0 0 4px", fontSize: 20 }}>Project Budgeting sync</h2>
      <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--on-variant)" }}>
        Project assignments are managed in Project Budgeting and synced here. Failed syncs and unmatched employee IDs show below.
      </p>
      <ProjectSyncStatusCard />
    </div>
  );
}
