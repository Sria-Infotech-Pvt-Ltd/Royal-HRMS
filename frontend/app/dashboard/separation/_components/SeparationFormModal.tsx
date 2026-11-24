"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import type { SeparationLookupOption, SeparationRequest, SeparationTypeOption } from "@/types/separation";
import { daysBetween, todayIso } from "../_workflow";
import EmployeePickerField, { type PickedEmployee } from "./EmployeePickerField";
import DateInput from "@/components/shared/DateInput";

interface Props {
  mode:            "create" | "edit";
  existing?:       SeparationRequest; // required when mode === "edit"
  canPickEmployee: boolean;
  onClose:         () => void;
  onSaved:         (request: SeparationRequest) => void;
}

interface FormState {
  separationType:         string;
  reason:                 string;
  reasonNote:             string;
  requestDate:            string;
  proposedLastWorkingDay: string;
  noticePeriodDays:       string;
  comments:               string;
}

type FormErrors = Partial<Record<keyof FormState | "document" | "submit", string>>;

const ALLOWED_DOC_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_DOC_BYTES = 5 * 1024 * 1024;

function initialForm(existing?: SeparationRequest): FormState {
  if (!existing) {
    return {
      separationType: "", reason: "", reasonNote: "", requestDate: todayIso(),
      proposedLastWorkingDay: "", noticePeriodDays: "30", comments: "",
    };
  }
  return {
    separationType: existing.separation_type, reason: existing.reason, reasonNote: existing.reason_note,
    requestDate: existing.request_date, proposedLastWorkingDay: existing.proposed_last_working_day,
    noticePeriodDays: String(existing.notice_period_days), comments: existing.comments,
  };
}

export default function SeparationFormModal({ mode, existing, canPickEmployee, onClose, onSaved }: Props) {
  const t = useT();
  const { data: types }   = useFetch<SeparationTypeOption[]>(API.separation.types);
  const { data: reasons } = useFetch<SeparationLookupOption[]>(API.separation.reasons);

  const [employee, setEmployee] = useState<PickedEmployee | null>(null);
  const [form,       setForm]       = useState<FormState>(initialForm(existing));
  const [errors,     setErrors]     = useState<FormErrors>({});
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Which fields actually apply to the currently-selected type — nothing
  // is shown/required until a type is picked, matching how neither field
  // makes sense to ask about in the abstract (see backend
  // SEPARATION_REASON_APPLICABLE_TYPES's own comment).
  const selectedType = (types ?? []).find(option => option.value === form.separationType);
  const reasonApplicable = selectedType?.reason_applicable ?? false;
  const noticeApplicable = selectedType?.notice_period_applicable ?? false;

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  function handleTypeChange(value: string) {
    const next = (types ?? []).find(option => option.value === value);
    setForm(prev => ({
      ...prev,
      separationType: value,
      reason: next?.reason_applicable ? prev.reason : "",
      reasonNote: next?.reason_applicable ? prev.reasonNote : "",
      noticePeriodDays: next?.notice_period_applicable ? (prev.noticePeriodDays || "30") : "0",
    }));
    setErrors(prev => ({ ...prev, separationType: undefined, reason: undefined, reasonNote: undefined, noticePeriodDays: undefined }));
  }

  function handleReasonChange(value: string) {
    setForm(prev => ({ ...prev, reason: value, reasonNote: value === "other" ? prev.reasonNote : "" }));
    setErrors(prev => ({ ...prev, reason: undefined, reasonNote: undefined }));
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_DOC_BYTES) {
      setErrors(prev => ({ ...prev, document: t("\"{name}\" exceeds 5 MB.", { name: file.name }) }));
      return;
    }
    if (!ALLOWED_DOC_TYPES.includes(file.type)) {
      setErrors(prev => ({ ...prev, document: t("\"{name}\" must be PDF, JPG, or PNG.", { name: file.name }) }));
      return;
    }
    setDocumentFile(file);
    setErrors(prev => ({ ...prev, document: undefined }));
  }

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.separationType)         errs.separationType = t("Please select a separation type.");
    if (reasonApplicable && !form.reason) errs.reason      = t("Please select a reason.");
    if (reasonApplicable && form.reason === "other" && !form.reasonNote.trim())
      errs.reasonNote = t("Specify the reason, or pick a different option from the list.");
    if (!form.requestDate)            errs.requestDate    = t("Request date is required.");
    if (!form.proposedLastWorkingDay) errs.proposedLastWorkingDay = t("Proposed last working day is required.");
    else if (form.requestDate && form.proposedLastWorkingDay < form.requestDate)
      errs.proposedLastWorkingDay = t("Cannot be earlier than the request date.");
    if (noticeApplicable) {
      const notice = Number(form.noticePeriodDays);
      if (!form.noticePeriodDays || Number.isNaN(notice) || notice < 0) errs.noticePeriodDays = t("Enter a valid number of days.");
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const fields: Record<string, string> = {
        separation_type: form.separationType,
        reason: reasonApplicable ? form.reason : "",
        reason_note: reasonApplicable && form.reason === "other" ? form.reasonNote.trim() : "",
        request_date: form.requestDate,
        proposed_last_working_day: form.proposedLastWorkingDay,
        notice_period_days: noticeApplicable ? form.noticePeriodDays : "0",
        comments: form.comments.trim(),
      };
      if (mode === "create" && employee) fields.employee_id = employee.code;
      if (mode === "edit") fields.action = "update";

      let response;
      if (documentFile) {
        const fd = new FormData();
        Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
        fd.append("document", documentFile);
        response = mode === "create"
          ? await clientApi.post(API.separation.list, fd, { headers: { "Content-Type": "multipart/form-data" } })
          : await clientApi.patch(API.separation.detail(existing!.id), fd, { headers: { "Content-Type": "multipart/form-data" } });
      } else {
        response = mode === "create"
          ? await clientApi.post(API.separation.list, fields)
          : await clientApi.patch(API.separation.detail(existing!.id), fields);
      }
      onSaved(response.data?.data ?? response.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? t("Failed to submit the separation request. Please try again.");
      setErrors(prev => ({ ...prev, submit: msg }));
    } finally {
      setSubmitting(false);
    }
  }

  const noticeDays = form.requestDate && form.proposedLastWorkingDay
    ? daysBetween(form.requestDate, form.proposedLastWorkingDay) : null;

  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside a field and releasing past the modal's edge would otherwise land
  // on the overlay and close it mid-input. Only close when the gesture both
  // started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="modal-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="modal modal-lg" style={{ maxHeight: "92vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-logout" style={{ marginRight: 8 }} />
            {mode === "create" ? t("Request Separation") : t("Edit Separation Request")}
          </div>
          <button className="modal-close" onClick={onClose} suppressHydrationWarning aria-label={t("Close")}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {errors.submit && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <i className="ti ti-alert-circle" /><div>{errors.submit}</div>
            </div>
          )}

          {mode === "create" && canPickEmployee && (
            <div className="field-group mb-16">
              <label className="field-label">{t("Employee")}</label>
              <EmployeePickerField value={employee} onChange={setEmployee} />
              <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                {t("Leave blank to file this request for yourself.")}
              </p>
            </div>
          )}

          {mode === "edit" && (
            <div className="field-group mb-16">
              <label className="field-label">{t("Employee")}</label>
              <input className="field-input" value={`${existing!.employee_name} · ${existing!.employee_code}`} disabled />
            </div>
          )}

          <div className={`form-row ${reasonApplicable ? "cols-2" : ""}`}>
            <div className="field-group">
              <label className="field-label">
                {t("Separation Type")} <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                className={`field-input field-select${errors.separationType ? " field-error" : ""}`}
                value={form.separationType}
                onChange={e => handleTypeChange(e.target.value)}
              >
                <option value="">{t("Select type…")}</option>
                {(types ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {errors.separationType && <p className="field-error-msg">{errors.separationType}</p>}
            </div>
            {reasonApplicable && (
              <div className="field-group">
                <label className="field-label">
                  {t("Reason")} <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <select
                  className={`field-input field-select${errors.reason ? " field-error" : ""}`}
                  value={form.reason}
                  onChange={e => handleReasonChange(e.target.value)}
                >
                  <option value="">{t("Select reason…")}</option>
                  {(reasons ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                {errors.reason && <p className="field-error-msg">{errors.reason}</p>}
              </div>
            )}
          </div>

          {reasonApplicable && form.reason === "other" && (
            <div className="form-row">
              <div className="field-group">
                <label className="field-label">
                  {t("Specify Reason")} <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  className={`field-input${errors.reasonNote ? " field-error" : ""}`}
                  placeholder={t("e.g. Family relocation to another country")}
                  value={form.reasonNote}
                  onChange={e => setField("reasonNote", e.target.value)}
                />
                {errors.reasonNote && <p className="field-error-msg">{errors.reasonNote}</p>}
              </div>
            </div>
          )}

          <div className={`form-row ${noticeApplicable ? "cols-3" : "cols-2"}`}>
            <div className="field-group">
              <label className="field-label">
                {t("Request Date")} <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <DateInput className={`field-input${errors.requestDate ? " field-error" : ""}`} value={form.requestDate} onChange={isoDate => setField("requestDate", isoDate)} />
              {errors.requestDate && <p className="field-error-msg">{errors.requestDate}</p>}
            </div>
            <div className="field-group">
              <label className="field-label">
                {t("Proposed Last Working Day")} <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <DateInput className={`field-input${errors.proposedLastWorkingDay ? " field-error" : ""}`} value={form.proposedLastWorkingDay} onChange={isoDate => setField("proposedLastWorkingDay", isoDate)} />
              {errors.proposedLastWorkingDay
                ? <p className="field-error-msg">{errors.proposedLastWorkingDay}</p>
                : noticeDays !== null && <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>{noticeDays === 1 ? t("{count} day from request date", { count: noticeDays }) : t("{count} days from request date", { count: noticeDays })}</p>}
            </div>
            {noticeApplicable && (
              <div className="field-group">
                <label className="field-label">
                  {t("Notice Period (days)")} <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  type="number" min="0" className={`field-input${errors.noticePeriodDays ? " field-error" : ""}`}
                  value={form.noticePeriodDays} onChange={e => setField("noticePeriodDays", e.target.value)}
                />
                {errors.noticePeriodDays && <p className="field-error-msg">{errors.noticePeriodDays}</p>}
              </div>
            )}
          </div>

          <div className="field-group mb-16">
            <label className="field-label">{t("Comments")}</label>
            <textarea
              className="field-input" rows={3} style={{ resize: "vertical" }}
              value={form.comments} onChange={e => setField("comments", e.target.value)}
              placeholder={t("Optional notes for the record…")}
            />
          </div>

          <div className="field-group">
            <label className="field-label">{t("Supporting Document")}</label>
            {existing?.document_url && !documentFile && (
              <p style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
                {t("A document is already attached. Choosing a new file replaces it.")}
              </p>
            )}
            <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer", width: "fit-content" }}>
              <i className="ti ti-upload" /> {documentFile?.name ?? t("Choose file…")}
              <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png" onChange={handleFile} />
            </label>
            <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>{t("PDF, JPG, or PNG — up to 5 MB.")}</p>
            {errors.document && <p className="field-error-msg">{errors.document}</p>}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting} suppressHydrationWarning>
            {t("Cancel")}
          </button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting} suppressHydrationWarning>
            {submitting
              ? <><i className="ti ti-loader-2 spin" /> {t("Submitting…")}</>
              : <><i className="ti ti-send" /> {mode === "create" ? t("Submit Request") : t("Save Changes")}</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
