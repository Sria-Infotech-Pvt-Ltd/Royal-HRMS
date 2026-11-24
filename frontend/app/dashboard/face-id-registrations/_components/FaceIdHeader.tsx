"use client";

import Link from "next/link";
import { useT } from "@/hooks/useI18n";

interface FaceIdHeaderProps {
  /** The organisation's one-line note on who registers Face IDs; empty until it loads. */
  note:   string
  onBack: () => void
}

/** Title, the organisation's note, a way back, and a shortcut to the requests waiting for approval. */
export default function FaceIdHeader({ note, onBack }: FaceIdHeaderProps) {
  const t = useT();
  return (
    <div className="page-header">
      <div>
        <div className="page-title">{t("Face ID Registrations")}</div>
        <div className="page-sub">{note || t("Register or update an employee's Face ID in person. It is approved immediately.")}</div>
      </div>
      <div className="page-actions">
        <Link className="btn btn-ghost" href="/dashboard/approvals"><i className="ti ti-checklist" /> {t("Pending requests")}</Link>
        <button type="button" className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> {t("Back")}</button>
      </div>
    </div>
  );
}
