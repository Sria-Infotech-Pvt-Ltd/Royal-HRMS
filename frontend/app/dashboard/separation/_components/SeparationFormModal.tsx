"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { SeparationLookupOption, SeparationRequest } from "@/types/separation";
import { daysBetween, todayIso } from "../_workflow";
import EmployeePickerField, { type PickedEmployee } from "./EmployeePickerField";

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
      separationType: "", reason: "", requestDate: todayIso(),
      proposedLastWorkingDay: "", noticePeriodDays: "30", comments: "",
    };
  }
  return {
    separationType: existing.separation_type, reason: existing.reason,
    requestDate: existing.request_date, proposedLastWorkingDay: existing.proposed_last_working_day,
    noticePeriodDays: String(existing.notice_period_days), comments: existing.comments,
  };
}

export default function SeparationFormModal({ mode, existing, canPickEmployee, onClose, onSaved }: Props) {
  const { data: types }   = useFetch<SeparationLookupOption[]>(API.separation.types);
  const { data: reasons } = useFetch<SeparationLookupOption[]>(API.separation.reasons);

  const [employee, setEmployee] = useState<PickedEmployee | null>(null);
  const [form,       setForm]       = useState<FormState>(initialForm(existing));
  const [errors,     setErrors]     = useState<FormErrors>({});
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_DOC_BYTES) {
      setErrors(prev => ({ ...prev, document: `"${file.name}" exceeds 5 MB.` }));
      return;
    }
    if (!ALLOWED_DOC_TYPES.includes(file.type)) {
      setErrors(prev => ({ ...prev, document: `"${file.name}" must be PDF, JPG, or PNG.` }));
      return;
    }
    setDocumentFile(file);
    setErrors(prev => ({ ...prev, document: undefined }));
  }

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.separationType)         errs.separationType = "Please select a separation type.";
    if (!form.reason)                 errs.reason         = "Please select a reason.";
    if (!form.requestDate)            errs.requestDate    = "Request date is required.";
    if (!form.proposedLastWorkingDay) errs.proposedLastWorkingDay = "Proposed last working day is required.";
    else if (form.requestDate && form.proposedLastWorkingDay < form.requestDate)
      errs.proposedLastWorkingDay = "Cannot be earlier than the request date.";
    const notice = Number(form.noticePeriodDays);
    if (!form.noticePeriodDays || Number.isNaN(notice) || notice < 0) errs.noticePeriodDays = "Enter a valid number of days.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const fields: Record<string, string> = {
        separation_type: form.separationType,
        reason: form.reason,
        request_date: form.requestDate,
        proposed_last_working_day: form.proposedLastWorkingDay,
        notice_period_days: form.noticePeriodDays,
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
        ?.response?.data?.message ?? "Failed to submit the separation request. Please try again.";
      setErrors(prev => ({ ...prev, submit: msg }));
    } finally {
      setSubmitting(false);
    }
  }

  const noticeDays = form.requestDate && form.proposedLastWorkingDay
    ? daysBetween(form.requestDate, form.proposedLastWorkingDay) : null;

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal modal-lg" style={{ maxHeight: "92vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-logout" style={{ marginRight: 8 }} />
            {mode === "create" ? "Request Separation" : "Edit Separation Request"}
          </div>
          <button className="modal-close" onClick={onClose} suppressHydrationWarning>
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
              <label className="field-label">Employee</label>
              <EmployeePickerField value={employee} onChange={setEmployee} />
              <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                Leave blank to file this request for yourself.
              </p>
            </div>
          )}

          {mode === "edit" && (
            <div className="field-group mb-16">
              <label className="field-label">Employee</label>
              <input className="field-input" value={`${existing!.employee_name} · ${existing!.employee_code}`} disabled />
            </div>
          )}

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">
                Separation Type <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                className={`field-input field-select${errors.separationType ? " field-error" : ""}`}
                value={form.separationType}
                onChange={e => setField("separationType", e.target.value)}
              >
                <option value="">Select type…</option>
                {(types ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {errors.separationType && <p className="field-error-msg">{errors.separationType}</p>}
            </div>
            <div className="field-group">
              <label className="field-label">
                Reason <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                className={`field-input field-select${errors.reason ? " field-error" : ""}`}
                value={form.reason}
                onChange={e => setField("reason", e.target.value)}
              >
                <option value="">Select reason…</option>
                {(reasons ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {errors.reason && <p className="field-error-msg">{errors.reason}</p>}
            </div>
          </div>

          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">
                Request Date <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="date" className={`field-input${errors.requestDate ? " field-error" : ""}`}
                value={form.requestDate} onChange={e => setField("requestDate", e.target.value)}
              />
              {errors.requestDate && <p className="field-error-msg">{errors.requestDate}</p>}
            </div>
            <div className="field-group">
              <label className="field-label">
                Proposed Last Working Day <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="date" className={`field-input${errors.proposedLastWorkingDay ? " field-error" : ""}`}
                value={form.proposedLastWorkingDay} onChange={e => setField("proposedLastWorkingDay", e.target.value)}
              />
              {errors.proposedLastWorkingDay
                ? <p className="field-error-msg">{errors.proposedLastWorkingDay}</p>
                : noticeDays !== null && <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>{noticeDays} day{noticeDays !== 1 ? "s" : ""} from request date</p>}
            </div>
            <div className="field-group">
              <label className="field-label">
                Notice Period (days) <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="number" min="0" className={`field-input${errors.noticePeriodDays ? " field-error" : ""}`}
                value={form.noticePeriodDays} onChange={e => setField("noticePeriodDays", e.target.value)}
              />
              {errors.noticePeriodDays && <p className="field-error-msg">{errors.noticePeriodDays}</p>}
            </div>
          </div>

          <div className="field-group mb-16">
            <label className="field-label">Comments</label>
            <textarea
              className="field-input" rows={3} style={{ resize: "vertical" }}
              value={form.comments} onChange={e => setField("comments", e.target.value)}
              placeholder="Optional notes for the record…"
            />
          </div>

          <div className="field-group">
            <label className="field-label">Supporting Document</label>
            {existing?.document_url && !documentFile && (
              <p style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
                A document is already attached. Choosing a new file replaces it.
              </p>
            )}
            <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer", width: "fit-content" }}>
              <i className="ti ti-upload" /> {documentFile?.name ?? "Choose file…"}
              <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png" onChange={handleFile} />
            </label>
            <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>PDF, JPG, or PNG — up to 5 MB.</p>
            {errors.document && <p className="field-error-msg">{errors.document}</p>}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting} suppressHydrationWarning>
            Cancel
          </button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting} suppressHydrationWarning>
            {submitting
              ? <><i className="ti ti-loader-2 spin" /> Submitting…</>
              : <><i className="ti ti-send" /> {mode === "create" ? "Submit Request" : "Save Changes"}</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
