"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { OnboardingFieldConfig, UpdateOnboardingFieldPayload } from "@/types/onboardingFieldConfig";

interface Props {
  field: OnboardingFieldConfig;
  onClose: () => void;
  onSaved: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  text: "Text",
  textarea: "Long text",
  number: "Number",
  date: "Date",
  dropdown: "Dropdown",
  checkbox: "Checkbox",
  file: "File / Image",
};

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function EditFieldModal({ field, onClose, onSaved }: Props) {
  const [label, setLabel] = useState(field.label);
  const [optionsText, setOptionsText] = useState((field.options ?? []).join(", "));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isDropdown = field.field_type === "dropdown";

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!label.trim()) e.label = "Label is required.";
    if (isDropdown && !optionsText.trim()) e.options = "Add at least one option, separated by commas.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: UpdateOnboardingFieldPayload = {
      label: label.trim(),
      ...(isDropdown ? { options: optionsText.split(",").map(o => o.trim()).filter(Boolean) } : {}),
    };
    try {
      await clientApi.patch(API.settings.onboardingFields.detail(field.field_key), payload);
      onSaved();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to update field.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-pencil" style={{ marginRight: 8 }} />Edit Field</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Saving…</> : "Save"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}

      <div className="field-group mb-16">
        <label className="field-label">Field Label *</label>
        <input
          className={`field-input${errors.label ? " field-error" : ""}`}
          type="text"
          value={label}
          onChange={e => { setLabel(e.target.value); setErrors(prev => ({ ...prev, label: "" })); }}
        />
        {errors.label && <p className="field-error-msg">{errors.label}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Field Type</label>
        <div style={{ fontSize: 13, color: "var(--on-variant)", padding: "8px 0" }}>
          {TYPE_LABELS[field.field_type] ?? field.field_type}
        </div>
        <p style={{ fontSize: 11, color: "var(--on-variant)" }}>
          Type can&apos;t be changed after creation — it would corrupt any values already collected under it.
          {field.is_custom ? "" : " Built-in fields can't change type at all."}
        </p>
      </div>

      {isDropdown && (
        <div className="field-group">
          <label className="field-label">Dropdown Options *</label>
          <input
            className={`field-input${errors.options ? " field-error" : ""}`}
            type="text"
            placeholder="e.g. Option A, Option B, Option C"
            value={optionsText}
            onChange={e => { setOptionsText(e.target.value); setErrors(prev => ({ ...prev, options: "" })); }}
          />
          {errors.options
            ? <p className="field-error-msg">{errors.options}</p>
            : <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>Separate options with commas.</p>
          }
        </div>
      )}
    </Modal>
  );
}
