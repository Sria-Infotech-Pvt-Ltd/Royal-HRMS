"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { CreateOnboardingFieldPayload, OnboardingFieldType } from "@/types/onboardingFieldConfig";

interface Props {
  step: number;
  onClose: () => void;
  onCreated: () => void;
}

const TYPE_OPTIONS: { value: OnboardingFieldType; label: string }[] = [
  { value: "text",     label: "Text" },
  { value: "textarea", label: "Long text" },
  { value: "number",   label: "Number" },
  { value: "date",     label: "Date" },
  { value: "dropdown", label: "Dropdown" },
  { value: "checkbox", label: "Checkbox" },
  { value: "file",     label: "File / Image" },
];

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AddFieldModal({ step, onClose, onCreated }: Props) {
  const [label, setLabel] = useState("");
  const [fieldType, setFieldType] = useState<OnboardingFieldType>("text");
  const [optionsText, setOptionsText] = useState("");
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [required, setRequired] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!label.trim()) e.label = "Label is required.";
    if (fieldType === "dropdown" && !optionsText.trim()) {
      e.options = "Add at least one option, separated by commas.";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: CreateOnboardingFieldPayload = {
      label: label.trim(),
      field_type: fieldType,
      step,
      required,
      options: fieldType === "dropdown"
        ? optionsText.split(",").map(o => o.trim()).filter(Boolean)
        : [],
      allow_multiple: fieldType === "file" ? allowMultiple : false,
    };
    try {
      await clientApi.post(API.settings.onboardingFields.list, payload);
      onCreated();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to create field.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-plus" style={{ marginRight: 8 }} />Add Custom Field</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Creating…</> : "Create Field"}
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
          placeholder="e.g. Blood Donor Card Number"
          value={label}
          onChange={e => { setLabel(e.target.value); setErrors(prev => ({ ...prev, label: "" })); }}
        />
        {errors.label && <p className="field-error-msg">{errors.label}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Field Type</label>
        <select
          className="field-input field-select"
          value={fieldType}
          onChange={e => setFieldType(e.target.value as OnboardingFieldType)}
        >
          {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {fieldType === "dropdown" && (
        <div className="field-group mb-16">
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

      {fieldType === "file" && (
        <label className="module-check mb-16">
          <input type="checkbox" checked={allowMultiple} onChange={e => setAllowMultiple(e.target.checked)} />
          <span>Allow multiple files</span>
        </label>
      )}

      <label className="module-check">
        <input type="checkbox" checked={required} onChange={e => setRequired(e.target.checked)} />
        <span>Required</span>
      </label>
    </Modal>
  );
}
