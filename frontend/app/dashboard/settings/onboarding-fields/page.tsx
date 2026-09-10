"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import { ONBOARDING_STEP_LABELS, type OnboardingFieldConfig, type OnboardingSection } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import FieldConfigTable from "./_components/FieldConfigTable";
import AddFieldModal from "./_components/AddFieldModal";
import EditFieldModal from "./_components/EditFieldModal";
import AddSectionModal from "./_components/AddSectionModal";
import DocumentTypeConfigTable from "./_components/DocumentTypeConfigTable";
import AddDocumentTypeModal from "./_components/AddDocumentTypeModal";
import EducationExperienceFieldConfigTable from "./_components/EducationExperienceFieldConfigTable";

// Steps 0-3 are OnboardingFieldConfig (built-in); DOCUMENTS_STEP is a UI-only
// sentinel for the last tab, backed by the separate DocumentTypeConfig model.
// Any HR-created OnboardingSection (step 5+) renders as its own tab in
// between — see buildTabs() below.
const DOCUMENTS_STEP = 4;
const BUILTIN_STEP_NUMBERS = new Set([0, 1, 2, 3]);

// Education & Experience is no longer step 1 / OnboardingFieldConfig-backed
// — both wizards rebuilt it as bespoke add/remove lists (EducationChecklist.tsx
// / ExperienceList.tsx), so its settings now come from the separate
// EducationExperienceFieldConfig model (show/require toggles on existing
// fields only, no add/reorder/delete — see that model's own docstring).
// -1 is a UI-only sentinel here, same convention as DOCUMENTS_STEP, never a
// real OnboardingFieldConfig step. BUILTIN_STEP_NUMBERS still includes 1 so
// a stray step-1 OnboardingSection override row is never mistaken for a
// deletable custom section.
const EDUCATION_EXPERIENCE_STEP = -1;
const BUILTIN_TABS: { step: number; label: string; icon: string }[] = [
  { step: 0, label: ONBOARDING_STEP_LABELS[0], icon: "ti-user" },
  { step: 2, label: ONBOARDING_STEP_LABELS[2], icon: "ti-building-bank" },
  { step: 3, label: ONBOARDING_STEP_LABELS[3], icon: "ti-phone" },
];
const EDUCATION_EXPERIENCE_TAB = { step: EDUCATION_EXPERIENCE_STEP, label: "Education & Experience", icon: "ti-school" };
const DOCUMENTS_TAB = { step: DOCUMENTS_STEP, label: "Documents", icon: "ti-files" };

interface Tab { step: number; label: string; icon: string; section?: OnboardingSection }

// Built-ins first, then active custom sections (in their own order), then
// Documents last — an object keyed by step number can't express this order
// once custom steps (5+) exist, since JS sorts integer-like keys numerically
// ahead of Documents' "4", so this builds an explicit ordered array instead.
// OnboardingSection also carries label/icon-override rows for the 4
// built-ins (seeded so their tab can be renamed here) — those are matched
// onto BUILTIN_TABS by step number rather than rendered as extra tabs.
function buildTabs(sections: OnboardingSection[]): Tab[] {
  const activeByStep = new Map(sections.filter(s => s.is_active).map(s => [s.step, s]));
  const builtinTabs: Tab[] = BUILTIN_TABS.map(b => {
    const override = activeByStep.get(b.step);
    return override
      ? { step: b.step, label: override.label, icon: override.icon, section: override }
      : { step: b.step, label: b.label, icon: b.icon };
  });
  const customTabs: Tab[] = sections
    .filter(s => s.is_active && !BUILTIN_STEP_NUMBERS.has(s.step))
    .slice()
    .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
    .map(s => ({ step: s.step, label: s.label, icon: s.icon, section: s }));
  // builtinTabs is [Personal, Bank, Emergency] (in that order, per
  // BUILTIN_TABS above) — Education & Experience is inserted right after
  // Personal to roughly match where it always sat before.
  return [builtinTabs[0], EDUCATION_EXPERIENCE_TAB, ...builtinTabs.slice(1), ...customTabs, DOCUMENTS_TAB];
}

export default function OnboardingFieldsPage() {
  const router = useRouter();
  const canEdit = usePermission("settings.edit");
  const { data: fields, loading, error, refetch } = useFetch<OnboardingFieldConfig[]>(API.settings.onboardingFields.list);
  const { data: sectionsData, loading: sectionsLoading, refetch: refetchSections } =
    useFetch<OnboardingSection[]>(API.settings.onboardingSections.list);
  const { data: docTypes, loading: docTypesLoading, error: docTypesError, refetch: refetchDocTypes } =
    useFetch<DocumentTypeConfig[]>(API.settings.documentTypes.list);
  const [step, setStep] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingField, setEditingField] = useState<OnboardingFieldConfig | null>(null);
  const [showAddSection, setShowAddSection] = useState(false);
  const [renamingSection, setRenamingSection] = useState<OnboardingSection | null>(null);
  const [sectionActionError, setSectionActionError] = useState<string | null>(null);
  const [deletingSectionId, setDeletingSectionId] = useState<string | null>(null);

  const tabs = buildTabs(sectionsData ?? []);
  const activeTab = tabs.find(t => t.step === step) ?? tabs[0];
  const isDocumentsTab = step === DOCUMENTS_STEP;
  const isEducationExperienceTab = step === EDUCATION_EXPERIENCE_STEP;
  const list = fields ?? [];
  const stepFields = list.filter(f => f.step === step).sort((a, b) => a.order - b.order);
  const sortedDocTypes = (docTypes ?? []).slice().sort((a, b) => a.order - b.order);

  async function handleDeleteSection(section: OnboardingSection) {
    if (!window.confirm(`Delete the "${section.label}" section? This can't be undone.`)) return;
    setSectionActionError(null);
    setDeletingSectionId(section.id);
    try {
      await clientApi.delete(API.settings.onboardingSections.detail(section.id));
      if (step === section.step) setStep(0);
      refetchSections();
    } catch (err: unknown) {
      setSectionActionError((err as { message?: string })?.message ?? "Failed to delete section.");
    } finally {
      setDeletingSectionId(null);
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Onboarding Fields</div>
          <div className="page-sub">
            Show, hide, or require fields and document types on the employee onboarding wizard —
            and add your own custom ones.
          </div>
        </div>
        <div className="page-actions">
          {canEdit && (
            <button className="btn btn-ghost" onClick={() => setShowAddSection(true)}>
              <i className="ti ti-layout-grid-add" /> Add Section
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {sectionActionError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{sectionActionError}</div>
        </div>
      )}

      <div className="tabs mb-16" style={{ flexWrap: "wrap", rowGap: 6 }}>
        {tabs.map(t => (
          <div key={t.step} style={{ display: "inline-flex", alignItems: "center" }}>
            <button
              className={`tab${step === t.step ? " active" : ""}`}
              onClick={() => setStep(t.step)}
            >
              <i className={`ti ${t.icon}`} /> {t.label}
            </button>
            {canEdit && t.section && (
              <>
                <button
                  title="Rename section"
                  onClick={() => setRenamingSection(t.section!)}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: "2px 4px", color: "var(--on-variant)" }}
                >
                  <i className="ti ti-pencil" style={{ fontSize: 13 }} />
                </button>
                {!BUILTIN_STEP_NUMBERS.has(t.step) && (
                <button
                  title="Delete section"
                  disabled={deletingSectionId === t.section.id}
                  onClick={() => handleDeleteSection(t.section!)}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: "2px 4px", color: "var(--error)" }}
                >
                  <i className="ti ti-trash" style={{ fontSize: 13 }} />
                </button>
                )}
              </>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className={`ti ${activeTab.icon}`} /> {activeTab.label}
          </div>
          {canEdit && !isEducationExperienceTab && (
            <button className="btn btn-filled btn-sm" onClick={() => setShowAddModal(true)}>
              <i className="ti ti-plus" /> {isDocumentsTab ? "Add Document Type" : "Add Custom Field"}
            </button>
          )}
        </div>

        {isDocumentsTab ? (
          <>
            {docTypesLoading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading document types…</div>}
            {docTypesError && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{docTypesError}</div>}
            {!docTypesLoading && !docTypesError && (
              <DocumentTypeConfigTable types={sortedDocTypes} canEdit={canEdit} onChanged={refetchDocTypes} />
            )}
          </>
        ) : isEducationExperienceTab ? (
          <EducationExperienceFieldConfigTable canEdit={canEdit} />
        ) : (
          <>
            {(loading || sectionsLoading) && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading fields…</div>}
            {error && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}
            {!loading && !sectionsLoading && !error && (
              <FieldConfigTable fields={stepFields} canEdit={canEdit} onChanged={refetch} onEdit={setEditingField} />
            )}
          </>
        )}
      </div>

      {showAddModal && isDocumentsTab && (
        <AddDocumentTypeModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => { setShowAddModal(false); refetchDocTypes(); }}
        />
      )}
      {showAddModal && !isDocumentsTab && (
        <AddFieldModal
          step={step}
          onClose={() => setShowAddModal(false)}
          onCreated={() => { setShowAddModal(false); refetch(); }}
        />
      )}
      {editingField && (
        <EditFieldModal
          field={editingField}
          onClose={() => setEditingField(null)}
          onSaved={() => { setEditingField(null); refetch(); }}
        />
      )}
      {showAddSection && (
        <AddSectionModal
          onClose={() => setShowAddSection(false)}
          onSaved={() => { setShowAddSection(false); refetchSections(); }}
        />
      )}
      {renamingSection && (
        <AddSectionModal
          section={renamingSection}
          onClose={() => setRenamingSection(null)}
          onSaved={() => { setRenamingSection(null); refetchSections(); }}
        />
      )}
    </>
  );
}
