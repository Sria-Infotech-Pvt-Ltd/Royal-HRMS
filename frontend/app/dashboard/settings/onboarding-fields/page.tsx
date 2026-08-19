"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import { ONBOARDING_STEP_LABELS, type OnboardingFieldConfig } from "@/types/onboardingFieldConfig";
import FieldConfigTable from "./_components/FieldConfigTable";
import AddFieldModal from "./_components/AddFieldModal";

const STEP_ICONS: Record<number, string> = {
  0: "ti-user",
  1: "ti-school",
  2: "ti-building-bank",
  3: "ti-phone",
};

export default function OnboardingFieldsPage() {
  const router = useRouter();
  const canEdit = usePermission("settings.edit");
  const { data: fields, loading, error, refetch } = useFetch<OnboardingFieldConfig[]>(API.settings.onboardingFields.list);
  const [step, setStep] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);

  const list = fields ?? [];
  const stepFields = list.filter(f => f.step === step).sort((a, b) => a.order - b.order);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Onboarding Fields</div>
          <div className="page-sub">
            Show, hide, or require fields on the employee onboarding wizard — and add your own custom fields.
            Documents (Step 5) aren&apos;t configured here.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      <div className="tabs mb-16">
        {Object.entries(ONBOARDING_STEP_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`tab${step === Number(key) ? " active" : ""}`}
            onClick={() => setStep(Number(key))}
          >
            <i className={`ti ${STEP_ICONS[Number(key)]}`} /> {label}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className={`ti ${STEP_ICONS[step]}`} /> {ONBOARDING_STEP_LABELS[step]}
          </div>
          {canEdit && (
            <button className="btn btn-filled btn-sm" onClick={() => setShowAddModal(true)}>
              <i className="ti ti-plus" /> Add Custom Field
            </button>
          )}
        </div>

        {loading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading fields…</div>}
        {error && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}

        {!loading && !error && (
          <FieldConfigTable fields={stepFields} canEdit={canEdit} onChanged={refetch} />
        )}
      </div>

      {showAddModal && (
        <AddFieldModal
          step={step}
          onClose={() => setShowAddModal(false)}
          onCreated={() => { setShowAddModal(false); refetch(); }}
        />
      )}
    </>
  );
}
