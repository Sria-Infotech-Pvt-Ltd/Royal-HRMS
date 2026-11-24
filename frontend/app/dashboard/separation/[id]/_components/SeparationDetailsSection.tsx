import { useT } from "@/hooks/useI18n";
import type { SeparationRequest } from "@/types/separation";
import { fmtDate } from "../../_workflow";

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      <input className="field-input" value={value || "—"} disabled />
    </div>
  );
}

export default function SeparationDetailsSection({ r }: { r: SeparationRequest }) {
  const t = useT();
  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-file-description" /> {t("Separation Details")}</span>
      </div>
      <div className="card-body">
        <div className="form-row cols-2">
          <ReadField label={t("Request Reference")} value={r.request_ref} />
          <ReadField label={t("Created By")} value={r.created_by_name} />
        </div>
        <div className="form-row cols-2">
          <ReadField label={t("Separation Type")} value={r.separation_type_display} />
          <ReadField label={t("Reason")} value={r.reason === "other" && r.reason_note ? r.reason_note : r.reason_display} />
        </div>
        <div className="form-row cols-2">
          <ReadField label={t("Request Date")} value={fmtDate(r.request_date)} />
          <ReadField label={t("Proposed Last Working Day")} value={fmtDate(r.proposed_last_working_day)} />
        </div>
        <ReadField label={t("Notice Period")} value={t("{count} days", { count: r.notice_period_days })} />
        <div className="field-group">
          <label className="field-label">{t("Comments")}</label>
          <textarea className="field-input" rows={2} value={r.comments || "—"} disabled style={{ resize: "vertical" }} />
        </div>
        {r.document_url && (
          <div className="field-group">
            <label className="field-label">{t("Document")}</label>
            <a href={r.document_url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm" style={{ width: "fit-content" }}>
              <i className="ti ti-file-download" /> {t("View / Download Document")}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
