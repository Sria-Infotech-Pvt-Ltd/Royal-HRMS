"use client";

// Documents step for the Hire wizard — real file uploads against the
// HireAction (see backend HireActionDocument), copied onto real
// EmployeeDocument rows at Stage 2 (HireActionCompleteView). PAN/Aadhaar
// uploaded here or from the Statutory step's own inline upload show up in
// both places, since both read/write the same underlying document list.

import DocUploadButton, { type HireDocument } from "@/components/DocUploadButton";

export type { HireDocument };

interface DocItem { key: string; label: string; required: boolean; category: string }

const DOC_ITEMS: DocItem[] = [
  { key: "pan_card",         label: "PAN Card",           required: true,  category: "Identity" },
  { key: "aadhaar_card",     label: "Aadhaar Card",       required: true,  category: "Identity" },
  { key: "passport_photo",   label: "Passport",           required: false, category: "Identity" },
  { key: "degree_certificate", label: "Degree Certificate", required: true, category: "Education & Experience" },
  { key: "experience_letter", label: "Experience Letter", required: false, category: "Education & Experience" },
  { key: "cancelled_cheque", label: "Cancelled Cheque",   required: true,  category: "Financial" },
  { key: "latest_payslips",  label: "Latest Payslips",    required: false, category: "Financial" },
  { key: "signed_offer_letter", label: "Signed Offer Letter", required: true, category: "Onboarding" },
  { key: "address_proof",    label: "Address Proof",      required: false, category: "Onboarding" },
];

export const REQUIRED_DOC_KEYS = DOC_ITEMS.filter(d => d.required).map(d => d.key);

export interface VerificationDraft {
  verification_status: string; verification_completed_on: string; verification_provider: string;
}
export const EMPTY_VERIFICATION: VerificationDraft = { verification_status: "not_initiated", verification_completed_on: "", verification_provider: "" };

interface Props {
  documents: HireDocument[];
  uploading: string | null;
  error: string;
  onUpload: (documentType: string, file: File) => void;
  onDelete: (doc: HireDocument) => void;
  verification: VerificationDraft;
  onVerificationChange: (v: VerificationDraft) => void;
}

// These two are attached per qualification/employer on the Education &
// Experience step (one certificate per entry, not one shared slot) — shown
// here as a rollup count instead of a single upload button, since there's
// no one "the" file to attach at this flat, step-level list.
const PER_ENTRY_TYPES = new Set(["degree_certificate", "experience_letter"]);

export default function DocumentsChecklistStep({ documents, uploading, error, onUpload, onDelete, verification, onVerificationChange }: Props) {
  const categories = Array.from(new Set(DOC_ITEMS.map(d => d.category)));
  const docFor = (key: string) => documents.find(d => d.document_type === key);
  const countFor = (key: string) => documents.filter(d => d.document_type === key).length;

  return (
    <div className="mstep on">
      {error && (
        <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>
      )}
      {categories.map(cat => (
        <div key={cat} className="mb-5">
          <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>{cat}</div>
          <div className="space-y-2">
            {DOC_ITEMS.filter(d => d.category === cat).map(d => (
              <div key={d.key} className="flex items-center justify-between px-3.5 py-3 rounded-lg border border-[var(--outline-v)]">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-semibold">{d.label}</span>
                  <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded" style={{
                    background: d.required ? "var(--error-c)" : "var(--bg-mid)",
                    color: d.required ? "var(--error)" : "var(--on-variant)",
                  }}>
                    {d.required ? "Required" : "Optional"}
                  </span>
                </div>
                {PER_ENTRY_TYPES.has(d.key) ? (
                  <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
                    {countFor(d.key) > 0
                      ? <span className="badge badge-success"><i className="ti ti-circle-check" /> {countFor(d.key)} attached</span>
                      : "Attach from Education & experience"}
                  </span>
                ) : (
                  <DocUploadButton
                    documentType={d.key}
                    label={d.label}
                    existing={docFor(d.key)}
                    uploading={uploading === d.key}
                    onUpload={onUpload}
                    onDelete={onDelete}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Background verification</div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Verification status</label>
          <select value={verification.verification_status}
            onChange={e => onVerificationChange({ ...verification, verification_status: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-[var(--surface)] cursor-pointer">
            <option value="not_initiated">Not initiated</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Completed on</label>
          <input type="date" value={verification.verification_completed_on}
            onChange={e => onVerificationChange({ ...verification, verification_completed_on: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-[var(--surface)]" />
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Provider / case reference</label>
          <input value={verification.verification_provider}
            onChange={e => onVerificationChange({ ...verification, verification_provider: e.target.value })}
            placeholder="Agency and reference" className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-[var(--surface)]" />
        </div>
      </div>
    </div>
  );
}
