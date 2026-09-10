"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type {
  CreateOnboardingSectionPayload, OnboardingSection, UpdateOnboardingSectionPayload,
} from "@/types/onboardingFieldConfig";

interface Props {
  section?: OnboardingSection; // present = rename existing, absent = create new
  onClose: () => void;
  onSaved: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AddSectionModal({ section, onClose, onSaved }: Props) {
  const isEdit = Boolean(section);
  const [label, setLabel] = useState(section?.label ?? "");
  const [icon, setIcon] = useState(section?.icon ?? "ti-folder");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!label.trim()) e.label = "Label is required.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      if (isEdit && section) {
        const payload: UpdateOnboardingSectionPayload = { label: label.trim(), icon: icon.trim() || "ti-folder" };
        await clientApi.patch(API.settings.onboardingSections.detail(section.id), payload);
      } else {
        const payload: CreateOnboardingSectionPayload = { label: label.trim(), icon: icon.trim() || "ti-folder" };
        await clientApi.post(API.settings.onboardingSections.list, payload);
      }
      onSaved();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to save section.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className={`ti ${isEdit ? "ti-pencil" : "ti-plus"}`} style={{ marginRight: 8 }} />{isEdit ? "Rename Section" : "Add Section"}</>}
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Saving…</> : isEdit ? "Save" : "Create Section"}
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
        <label className="field-label">Section Label *</label>
        <input
          className={`field-input${errors.label ? " field-error" : ""}`}
          type="text"
          placeholder="e.g. Company Assets"
          value={label}
          onChange={e => { setLabel(e.target.value); setErrors(prev => ({ ...prev, label: "" })); }}
        />
        {errors.label && <p className="field-error-msg">{errors.label}</p>}
      </div>

      <div className="field-group">
        <label className="field-label">Tab Icon</label>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 8, background: "var(--bg-low)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <i className={`ti ${icon || "ti-folder"}`} style={{ fontSize: 16 }} />
          </div>
          <input
            className="field-input"
            type="text"
            placeholder="ti-folder"
            value={icon}
            onChange={e => setIcon(e.target.value)}
          />
        </div>
        <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
          A Tabler icon class, e.g. ti-folder, ti-briefcase, ti-star.
        </p>
      </div>
    </Modal>
  );
}
