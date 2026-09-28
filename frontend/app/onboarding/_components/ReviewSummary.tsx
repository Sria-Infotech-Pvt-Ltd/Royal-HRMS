"use client";

// Final "Review & Submit" step — a read-only rollup of every earlier step,
// each with an Edit link that jumps straight back to it (StepIndicator's own
// isReachable gate already allows jumping backward to any already-done step,
// so this just calls the same onStepClick/setTab the stepper itself uses).
import type { WizardStep } from "../_wizardSteps";
import type { ProfileForm } from "../_types";
import type { OnboardingFieldConfigByStep } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import type { EducationEntry } from "./EducationChecklist";
import type { ExperienceEntry } from "./ExperienceList";
import type { FamilyEntry, NomineeEntry } from "./FamilyNominationStep";
import type { AssetEntry } from "./AssetsList";
import type { UploadedDoc } from "./TabDocuments";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

interface Props {
  steps: WizardStep[]; // full list, including this Review step itself (skipped when rendering)
  form: ProfileForm;
  customValues: Record<string, string>;
  fieldConfig: OnboardingFieldConfigByStep;
  educationEntries: EducationEntry[];
  experienceEntries: ExperienceEntry[];
  familyEntries: FamilyEntry[];
  nomineeEntries: NomineeEntry[];
  assetEntries: AssetEntry[];
  docTypes: DocumentTypeConfig[];
  docs: UploadedDoc[];
  faceRegistration: Partial<FaceRegistrationRequest> | null;
  faceMandatory: boolean;
  onEditStep: (index: number) => void;
}

function fieldValue(config: { field_key: string; is_custom: boolean }, form: ProfileForm, customValues: Record<string, string>): string {
  if (config.is_custom) return customValues[config.field_key] ?? "";
  return (form as unknown as Record<string, string>)[config.field_key] ?? "";
}

function Section({ title, onEdit, children }: { title: string; onEdit: () => void; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1.5rem", paddingBottom: "1.25rem", borderBottom: "1px solid var(--outline-v)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: ".75rem" }}>
        <div style={{ fontSize: ".82rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)" }}>
          {title}
        </div>
        <button type="button" onClick={onEdit} className="btn btn-ghost btn-sm" style={{ gap: 5 }}>
          <i className="ti ti-pencil" style={{ fontSize: 12 }} /> Edit
        </button>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: ".3rem 0", fontSize: ".85rem", borderBottom: "1px solid var(--outline-v)" }}>
      <span style={{ color: "var(--on-variant)" }}>{label}</span>
      <span style={{ fontWeight: 500, textAlign: "right" }}>{value?.trim() ? value : "—"}</span>
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: ".82rem", color: "var(--on-variant)", fontStyle: "italic" }}>{children}</p>;
}

export default function ReviewSummary({
  steps, form, customValues, fieldConfig,
  educationEntries, experienceEntries, familyEntries, nomineeEntries, assetEntries,
  docTypes, docs, faceRegistration, faceMandatory, onEditStep,
}: Props) {
  const uploadedTypes = new Set(docs.map(d => d.document_type));

  return (
    <div>
      <p style={{ fontSize: ".9rem", color: "var(--on-variant)", marginBottom: "1.5rem" }}>
        Review everything below before submitting. Use <strong>Edit</strong> on any section to go back and change it —
        nothing is sent to HR until you press <strong>Submit for Approval</strong>.
      </p>

      {steps.map((step, i) => {
        if (step.kind === "review") return null;

        if (step.kind === "fields") {
          const configs = (fieldConfig[String(step.step)] ?? []).filter(c => c.visible);
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {configs.length === 0
                ? <EmptyNote>Nothing configured for this section.</EmptyNote>
                : configs.map(c => <Row key={c.field_key} label={c.label} value={fieldValue(c, form, customValues)} />)
              }
            </Section>
          );
        }

        if (step.kind === "education") {
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {educationEntries.length === 0
                ? <EmptyNote>No education entries added.</EmptyNote>
                : educationEntries.map(e => (
                  <Row key={e.id} label={e.institution || "(institution not set)"}
                    value={[e.custom_level_label || e.level, e.percentage && `${e.percentage}%`].filter(Boolean).join(" · ")} />
                ))
              }
            </Section>
          );
        }

        if (step.kind === "experience") {
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {experienceEntries.length === 0
                ? <EmptyNote>No prior experience added.</EmptyNote>
                : experienceEntries.map(e => (
                  <Row key={e.id} label={`${e.employer_name || "(employer not set)"} — ${e.designation || "—"}`}
                    value={e.is_current ? "Current" : [e.start_date, e.end_date].filter(Boolean).join(" – ")} />
                ))
              }
            </Section>
          );
        }

        if (step.kind === "family-nomination") {
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {familyEntries.length === 0
                ? <EmptyNote>No family members added.</EmptyNote>
                : familyEntries.map(f => (
                  <Row key={f.id} label={`${f.name} (${f.relationship})`} value={f.is_dependent ? "Dependent" : "Not dependent"} />
                ))
              }
              {nomineeEntries.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {nomineeEntries.map(n => {
                    const member = familyEntries.find(f => f.id === n.family_member);
                    return <Row key={n.id} label={`Nominee: ${member?.name ?? "—"}`} value={`${n.scheme} · ${n.share_percentage}%`} />;
                  })}
                </div>
              )}
            </Section>
          );
        }

        if (step.kind === "assets") {
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {assetEntries.length === 0
                ? <EmptyNote>No assets added.</EmptyNote>
                : assetEntries.map(a => <Row key={a.id} label={a.asset_type} value={a.tag_number || a.condition} />)
              }
            </Section>
          );
        }

        if (step.kind === "documents") {
          const requiredMissing = docTypes.filter(t => t.required && !uploadedTypes.has(t.type_key));
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              {docTypes.map(t => (
                <Row key={t.type_key} label={`${t.label}${t.required ? " *" : ""}`}
                  value={uploadedTypes.has(t.type_key) ? "Uploaded" : "Not uploaded"} />
              ))}
              {requiredMissing.length > 0 && (
                <p style={{ fontSize: ".78rem", color: "var(--error)", marginTop: 6 }}>
                  <i className="ti ti-alert-triangle" /> Missing required: {requiredMissing.map(t => t.label).join(", ")}
                </p>
              )}
            </Section>
          );
        }

        if (step.kind === "face") {
          return (
            <Section key={step.label} title={step.label} onEdit={() => onEditStep(i)}>
              <Row label="Status" value={faceRegistration ? "Submitted" : faceMandatory ? "Required — not yet submitted" : "Optional — not submitted"} />
            </Section>
          );
        }

        return null;
      })}
    </div>
  );
}
