"use client";

import { useT } from "@/hooks/useI18n";

interface InterviewHeaderProps {
  /** Name of the company code the list is narrowed to, if any. */
  branchName?:   string
  canCreate:     boolean
  onBulkImport:  () => void
  onAdd:         () => void
}

/** Title, a one-line description and the two actions. Search and filters live in the toolbar below. */
export default function InterviewHeader({ branchName, canCreate, onBulkImport, onAdd }: InterviewHeaderProps) {
  const t = useT();
  return (
    <div className="page-header">
      <div>
        <div className="page-title">{t("Interview List")}</div>
        <div className="page-sub">
          {branchName
            ? <>{t("Showing candidates for")} <strong>{branchName}</strong></>
            : t("Track every candidate from first contact to onboarding")}
        </div>
      </div>
      {canCreate && (
        <div className="page-actions">
          <button type="button" className="btn btn-ghost" onClick={onBulkImport} suppressHydrationWarning>
            <i className="ti ti-file-upload" /> {t("Bulk Import")}
          </button>
          <button type="button" className="btn btn-filled" onClick={onAdd}>
            <i className="ti ti-plus" /> {t("Add Candidate")}
          </button>
        </div>
      )}
    </div>
  );
}
