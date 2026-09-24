"use client";

import DocUploadButton, { type HireDocument } from "@/components/DocUploadButton";
import CountrySelect from "@/components/CountrySelect";

export interface StatutoryDraft {
  pan_number: string; aadhaar_number: string; passport_number: string; passport_expiry: string;
  passport_issue_date: string; passport_place_of_issue: string; passport_country_of_issue: string;
  uan_number: string; esi_number: string; pf_covered: string; esi_covered: string;
  account_number: string; ifsc_code: string; bank_name: string; account_holder_name: string;
}

export const EMPTY_STATUTORY: StatutoryDraft = {
  pan_number: "", aadhaar_number: "", passport_number: "", passport_expiry: "",
  passport_issue_date: "", passport_place_of_issue: "", passport_country_of_issue: "",
  uan_number: "", esi_number: "", pf_covered: "true", esi_covered: "false",
  account_number: "", ifsc_code: "", bank_name: "", account_holder_name: "",
};

function Toggle({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="seg">
      {["true", "false"].map(v => (
        <button key={v} type="button" onClick={() => onChange(v)} aria-pressed={value === v}>
          {v === "true" ? "Yes" : "No"}
        </button>
      ))}
    </div>
  );
}

interface Props {
  value: StatutoryDraft;
  onChange: (v: StatutoryDraft) => void;
  documents: HireDocument[];
  uploading: string | null;
  docError: string;
  onUploadDoc: (documentType: string, file: File) => void;
  onDeleteDoc: (doc: HireDocument) => void;
}

export default function StatutoryAccountsStep({ value, onChange, documents, uploading, docError, onUploadDoc, onDeleteDoc }: Props) {
  function set<K extends keyof StatutoryDraft>(key: K, v: StatutoryDraft[K]) {
    onChange({ ...value, [key]: v });
  }
  const docFor = (key: string) => documents.find(d => d.document_type === key);

  return (
    <div className="mstep on">
      <div className="note warn" style={{ marginBottom: 16 }}>
        <b>Handled as sensitive data</b>
        Government IDs and bank details are stored encrypted, masked in the UI by default, and every reveal is written to the audit log.
      </div>

      {docError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{docError}</div></div>}

      <div className="sechead">GOVERNMENT IDS</div>
      <div className="g3">
        <div className="f">
          <label>PAN <span className="req">*</span></label>
          <input value={value.pan_number} onChange={e => set("pan_number", e.target.value.toUpperCase())} placeholder="ABCDE1234F" maxLength={10} className="finput" />
          <div style={{ marginTop: 6 }}>
            <DocUploadButton documentType="pan_card" label="PAN card" existing={docFor("pan_card")}
              uploading={uploading === "pan_card"} onUpload={onUploadDoc} onDelete={onDeleteDoc} />
          </div>
        </div>
        <div className="f">
          <label>Aadhaar <span className="req">*</span></label>
          <input value={value.aadhaar_number} onChange={e => set("aadhaar_number", e.target.value.replace(/\D/g, ""))} placeholder="XXXX XXXX XXXX" maxLength={12} className="finput" />
          <div style={{ marginTop: 6 }}>
            <DocUploadButton documentType="aadhaar_card" label="Aadhaar card" existing={docFor("aadhaar_card")}
              uploading={uploading === "aadhaar_card"} onUpload={onUploadDoc} onDelete={onDeleteDoc} />
          </div>
        </div>
        <div className="f">
          <label>Passport <span className="tag">OPTIONAL</span></label>
          <input value={value.passport_number} onChange={e => set("passport_number", e.target.value)} placeholder="Optional" className="finput" />
          <div style={{ marginTop: 6 }}>
            <DocUploadButton documentType="passport_photo" label="passport" existing={docFor("passport_photo")}
              uploading={uploading === "passport_photo"} onUpload={onUploadDoc} onDelete={onDeleteDoc} />
          </div>
        </div>
        <div className="f">
          <label>Passport issue date <span className="tag">OPTIONAL</span></label>
          <input type="date" value={value.passport_issue_date} onChange={e => set("passport_issue_date", e.target.value)} disabled={!value.passport_number} className="finput" />
        </div>
        <div className="f">
          <label>Passport expiry <span className="tag">OPTIONAL</span></label>
          <input type="date" value={value.passport_expiry} onChange={e => set("passport_expiry", e.target.value)} disabled={!value.passport_number} className="finput" />
          {value.passport_issue_date && value.passport_expiry && value.passport_expiry <= value.passport_issue_date && (
            <div className="hint" style={{ color: "var(--error)" }}>Expiry must be after the issue date.</div>
          )}
        </div>
        <div className="f">
          <label>Place of issue <span className="tag">OPTIONAL</span></label>
          <input value={value.passport_place_of_issue} onChange={e => set("passport_place_of_issue", e.target.value)} placeholder="e.g. Hyderabad" disabled={!value.passport_number} className="finput" />
        </div>
        <div className="f">
          <label>Country of issue <span className="tag">OPTIONAL</span></label>
          <CountrySelect value={value.passport_country_of_issue} onChange={v => set("passport_country_of_issue", v)}
            mode="name" placeholder="Select country" />
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">PROVIDENT FUND</div>
      <div className="togline" style={{ marginBottom: 14 }}>
        <span>Covered under PF</span>
        <Toggle value={value.pf_covered} onChange={v => set("pf_covered", v)} />
      </div>
      <div className="g3">
        <div className="f">
          <label>UAN <span className="tag">OPTIONAL</span></label>
          <input value={value.uan_number} onChange={e => set("uan_number", e.target.value.replace(/\D/g, ""))} placeholder="12 digits, if available" maxLength={12} className="finput" />
          <div className="hint">Leave blank for a first job — EPFO will allot one.</div>
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">ESI</div>
      <div className="togline" style={{ marginBottom: 14 }}>
        <span>Covered under ESI</span>
        <Toggle value={value.esi_covered} onChange={v => set("esi_covered", v)} />
      </div>
      {value.esi_covered === "true" && (
        <div className="g3">
          <div className="f">
            <label>ESI number <span className="tag">OPTIONAL</span></label>
            <input value={value.esi_number} onChange={e => set("esi_number", e.target.value.replace(/\D/g, ""))} placeholder="10 digits, if available" maxLength={10} className="finput" />
          </div>
        </div>
      )}

      <div className="divider" />
      <div className="sechead">BANK ACCOUNT</div>
      <div className="g3">
        <div className="f">
          <label>Account holder name <span className="req">*</span></label>
          <input value={value.account_holder_name} onChange={e => set("account_holder_name", e.target.value)} placeholder="Should match the PAN name" className="finput" />
        </div>
        <div className="f">
          <label>Account number <span className="req">*</span></label>
          <input value={value.account_number} onChange={e => set("account_number", e.target.value.replace(/\D/g, ""))} className="finput" />
        </div>
        <div className="f">
          <label>IFSC code <span className="req">*</span></label>
          <input value={value.ifsc_code} onChange={e => set("ifsc_code", e.target.value.toUpperCase())} placeholder="HDFC0001234" maxLength={11} className="finput" />
        </div>
        <div className="f">
          <label>Bank name <span className="tag">OPTIONAL</span></label>
          <input value={value.bank_name} onChange={e => set("bank_name", e.target.value)} placeholder="e.g. HDFC Bank" className="finput" />
        </div>
      </div>
    </div>
  );
}
