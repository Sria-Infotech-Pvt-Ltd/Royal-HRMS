"use client";

import type { ProfileForm } from "@/app/onboarding/_types";
import type { EducationEntry } from "@/app/onboarding/_components/EducationChecklist";
import type { ExperienceEntry } from "@/app/onboarding/_components/ExperienceList";
import type { FamilyEntry, NomineeEntry } from "@/app/onboarding/_components/FamilyNominationStep";
import type { AssetEntry } from "@/app/onboarding/_components/AssetsList";
import type { EmploymentDraft } from "./EmploymentStep";
import type { BasicPayDraft } from "./BasicPayStep";
import type { StatutoryDraft } from "./StatutoryAccountsStep";
import { REQUIRED_DOC_LABELS } from "./DocumentsChecklistStep";

interface Props {
  reservedEmployeeId: string;
  positionTitle: string;
  orgUnitName: string;
  grade: string;
  effectiveFrom: string;
  firstName: string;
  lastName: string;
  form: ProfileForm;
  employment: EmploymentDraft;
  basicPay: BasicPayDraft;
  statutory: StatutoryDraft;
  emergencyContactCount: number;
  panNumber: string;
  aadhaarNumber: string;
  familyEntries: FamilyEntry[];
  nomineeEntries: NomineeEntry[];
  educationEntries: EducationEntry[];
  experienceEntries: ExperienceEntry[];
  assetEntries: AssetEntry[];
  uploadedDocTypes: Set<string>;
  requiredDocTypes: string[];
  onHire: () => void;
  hiring: boolean;
  hireError: string | null;
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <b className={warn ? "warn" : ""}>{value || "—"}</b>
    </div>
  );
}

export default function ReviewStep(props: Props) {
  const {
    reservedEmployeeId, positionTitle, orgUnitName, grade, effectiveFrom, firstName, lastName,
    form, employment, basicPay, statutory, emergencyContactCount, panNumber, aadhaarNumber, familyEntries, nomineeEntries,
    educationEntries, experienceEntries, assetEntries, uploadedDocTypes, requiredDocTypes,
    onHire, hiring, hireError,
  } = props;

  const missingRequiredDocs = requiredDocTypes.filter(t => !uploadedDocTypes.has(t));
  const nomineeTotals: Record<string, number> = {};
  for (const n of nomineeEntries) {
    const scheme = n.scheme || "epf_eps";
    nomineeTotals[scheme] = (nomineeTotals[scheme] ?? 0) + (Number(n.share_percentage) || 0);
  }
  const overSharedScheme = Object.entries(nomineeTotals).find(([, total]) => total > 100);

  // Mirrors HireActionCompleteView's own server-side check (the real gate —
  // this is just so the button reflects it immediately instead of only
  // failing after a round trip). Anything appearing here blocks hiring;
  // this is no longer "can finish later" advisory text.
  const blockingReasons: string[] = [];
  if (!firstName.trim()) blockingReasons.push("First name");
  if (!lastName.trim()) blockingReasons.push("Last name");
  if (!form.date_of_birth) blockingReasons.push("Date of birth");
  if (!form.gender) blockingReasons.push("Gender");
  if (!employment.employment_type) blockingReasons.push("Employment type");
  if (!employment.role) blockingReasons.push("Role");
  if (!employment.branch) blockingReasons.push("Company code");
  if (!panNumber.trim()) blockingReasons.push("PAN");
  if (!aadhaarNumber.trim()) blockingReasons.push("Aadhaar");
  if (!statutory.account_holder_name.trim()) blockingReasons.push("Account holder name");
  if (!statutory.account_number.trim()) blockingReasons.push("Account number");
  if (!statutory.ifsc_code.trim()) blockingReasons.push("IFSC code");
  // The shared EducationChecklist component's own copy ("at least one is
  // required before you can submit") was never actually enforced anywhere
  // in this wizard — QA report #39 caught the step passing through empty.
  // Enforcing it here at Review matches what that text already promises.
  if (!educationEntries.some(e => e.institution?.trim())) blockingReasons.push("At least one education entry");
  if (missingRequiredDocs.length) blockingReasons.push(`${missingRequiredDocs.length} required document(s)`);
  if (overSharedScheme) blockingReasons.push(`nominee shares for ${overSharedScheme[0]} exceed 100%`);

  const notPayrollReasons: string[] = [];
  if (!form.father_name?.trim()) notPayrollReasons.push("father/mother's name is missing (EPF Form 2)");

  const fieldsFilled = [
    firstName, lastName, form.date_of_birth, form.gender, employment.employment_type,
    employment.role, employment.branch, panNumber,
  ].filter(Boolean).length;
  const completeness = Math.round((fieldsFilled / 8) * 100);

  return (
    <div className="mstep on">
      {/* QA report #50 — this used to say "Ready to hire" unconditionally,
          even with 10 blocking items still listed right below it. Now it
          only claims that when it's actually true. */}
      {blockingReasons.length === 0 ? (
        <div className="note info" style={{ marginBottom: 14 }}>
          <b>Ready to hire</b>
          The record is created in Onboarding status. Optional details (father/mother&apos;s name, non-required documents) can still be finished afterward.
        </div>
      ) : (
        <div className="note warn" style={{ marginBottom: 14, borderColor: "var(--error)" }}>
          <b>Not ready to hire — complete these first</b>
          {blockingReasons.join(", ")}.
        </div>
      )}

      <div className="kv" style={{ marginBottom: 6 }}>
        <span>Record completeness{completeness < 100 ? " · Not payroll ready" : ""}</span><b>{completeness}%</b>
      </div>
      <div className={`meter${completeness < 100 ? " mid" : ""}`} style={{ marginBottom: 16 }}>
        <i style={{ width: `${completeness}%` }} />
      </div>

      {notPayrollReasons.length > 0 && (
        <div className="note warn" style={{ marginBottom: 16 }}>
          <b>Not payroll ready</b>
          {notPayrollReasons.join("; ")} — the record can still be created in Onboarding status.
        </div>
      )}

      {hireError && (
        <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg border border-[var(--error-c)] mb-4"
          style={{ background: "var(--error-c)", color: "var(--error)" }}>
          <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
          <span className="text-[13px]">{hireError}</span>
        </div>
      )}

      <div className="g2" style={{ marginBottom: 16 }}>
        <div className="rvcard">
          <h4>PERSONAL</h4>
          <div className="kvlist">
            <Row label="Legal name" value={`${firstName} ${lastName}`.trim()} />
            <Row label="Date of birth" value={form.date_of_birth} />
            <Row label="Gender" value={form.gender ? form.gender[0].toUpperCase() + form.gender.slice(1) : ""} />
            <Row label="Marital status" value={form.marital_status} />
            <Row label="Father/mother" value={form.father_name} />
            <Row label="Current address" value={[form.current_village, form.current_state].filter(Boolean).join(", ")} />
            <Row
              label="Emergency contacts"
              value={emergencyContactCount > 0 ? `${emergencyContactCount} added` : "None added"}
              warn={emergencyContactCount < 2}
            />
          </div>
        </div>
        <div className="rvcard">
          <h4>EMPLOYMENT</h4>
          <div className="kvlist">
            <Row label="Employee number" value={reservedEmployeeId} />
            <Row label="Position" value={positionTitle} />
            <Row label="Org unit" value={orgUnitName} />
            <Row label="Grade / band" value={grade} />
            <Row label="Employment type" value={employment.employment_type} />
            <Row label="Date of joining" value={effectiveFrom} />
            <Row label="Work location" value={employment.work_location} />
            <Row label="Annual CTC" value={employment.annual_ctc ? `₹${Number(employment.annual_ctc).toLocaleString("en-IN")}` : ""} />
          </div>
        </div>
      </div>

      <div className="rvcard" style={{ marginBottom: 16 }}>
        <h4>STATUTORY &amp; ACCOUNTS</h4>
        <div className="g2">
          <div className="kvlist">
            <Row label="PAN" value={panNumber} warn={!panNumber} />
            <Row label="Aadhaar" value={aadhaarNumber} warn={!aadhaarNumber} />
            <Row label="Bank account" value={statutory.account_number ? `••••${statutory.account_number.slice(-4)}` : ""} />
            <Row label="IFSC / bank" value={statutory.bank_name ? `${statutory.ifsc_code} · ${statutory.bank_name}` : statutory.ifsc_code} />
          </div>
          <div className="kvlist">
            <Row label="Tax regime" value={basicPay.tax_regime === "old" ? "Old Regime" : "New Regime (115BAC)"} />
          </div>
        </div>
      </div>

      <div className="g2" style={{ marginBottom: 16 }}>
        <div className="rvcard">
          <h4>FAMILY &amp; NOMINATION</h4>
          <div className="kvlist">
            <Row label="Family members" value={String(familyEntries.length)} />
            <Row label="Nominees" value={String(nomineeEntries.length)} />
          </div>
        </div>
        <div className="rvcard">
          <h4>EDUCATION &amp; EXPERIENCE</h4>
          <div className="kvlist">
            <Row label="Qualifications" value={String(educationEntries.length)} warn={educationEntries.length === 0} />
            <Row label="Employers" value={String(experienceEntries.length)} />
          </div>
        </div>
      </div>

      <div className="g2" style={{ marginBottom: 20 }}>
        <div className="rvcard">
          <h4>DOCUMENTS</h4>
          <div className="kvlist">
            <Row label="Uploaded" value={`${uploadedDocTypes.size} of ${requiredDocTypes.length}`} />
            {missingRequiredDocs.length > 0 && (
              <Row label="Missing required" value={missingRequiredDocs.map(k => REQUIRED_DOC_LABELS[k] ?? k).join(", ")} warn />
            )}
          </div>
        </div>
        <div className="rvcard">
          <h4>ASSETS</h4>
          <div className="kvlist">
            <Row label="Assets to issue" value={String(assetEntries.length)} />
          </div>
        </div>
      </div>

      <button
        onClick={onHire}
        disabled={hiring || blockingReasons.length > 0}
        title={blockingReasons.length > 0 ? `Complete these first: ${blockingReasons.join(", ")}` : undefined}
        className="btn btn-filled"
      >
        {hiring ? "Hiring…" : "Hire employee →"}
      </button>
    </div>
  );
}
