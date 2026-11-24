"use client";

import { useT } from "@/hooks/useI18n";

interface ApprovalsHeaderProps {
  onBack:    () => void
  onRefresh: () => void
  isLoading: boolean
}

/** Title, a way back, and a refresh. */
export default function ApprovalsHeader({ onBack, onRefresh, isLoading }: ApprovalsHeaderProps) {
  const t = useT();
  return (
    <div className="page-header">
      <div>
        <div className="page-title">{t("Onboarding Approvals")}</div>
        <div className="page-sub">{t("Review and approve employee onboarding submissions")}</div>
      </div>
      <div className="page-actions">
        <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={isLoading} suppressHydrationWarning>
          <i className={`ti ti-refresh${isLoading ? " spin" : ""}`} /> {t("Refresh")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          <i className="ti ti-arrow-left" /> {t("Back")}
        </button>
      </div>
    </div>
  );
}
