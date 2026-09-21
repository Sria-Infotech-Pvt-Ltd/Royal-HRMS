"use client";

// Lightweight Documents checklist for the Hire wizard — matches the
// reference mockup's category groups exactly, but deliberately doesn't
// attempt real file storage before the employee exists (there's nowhere
// to put it yet). The mockup's own copy already says as much ("Remaining
// items can also be completed after the record is created") — real
// uploads happen afterward via the existing HR onboarding wizard
// (app/dashboard/employees/[id]/onboarding/), which already has working
// document upload against a real employee id.

interface DocItem { key: string; label: string; required: boolean; category: string }

const DOC_ITEMS: DocItem[] = [
  { key: "pan_card",         label: "PAN Card",           required: true,  category: "Identity" },
  { key: "aadhaar_card",     label: "Aadhaar Card",       required: true,  category: "Identity" },
  { key: "passport",         label: "Passport",           required: false, category: "Identity" },
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
  selected: Set<string>;
  onToggle: (key: string) => void;
  verification: VerificationDraft;
  onVerificationChange: (v: VerificationDraft) => void;
}

export default function DocumentsChecklistStep({ selected, onToggle, verification, onVerificationChange }: Props) {
  const categories = Array.from(new Set(DOC_ITEMS.map(d => d.category)));

  return (
    <div className="mstep on">
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
                <span className="badge badge-warn">{selected.has(d.key) ? "Selected" : "Pending"}</span>
                <button onClick={() => onToggle(d.key)}
                  className="px-3.5 py-1.5 rounded-lg text-[12px] font-medium border border-[var(--outline-v)] bg-[var(--surface)] hover:bg-[var(--bg-low)]">
                  {selected.has(d.key) ? "Selected" : "Choose file"}
                </button>
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
