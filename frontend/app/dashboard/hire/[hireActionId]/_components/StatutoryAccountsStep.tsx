"use client";

import { useEffect, useRef, useState } from "react";
import DocUploadButton, { type HireDocument } from "@/components/DocUploadButton";
import FieldError from "@/components/shared/FieldError";
import CountrySelect from "@/components/CountrySelect";
import DateInput from "@/components/shared/DateInput";
import { useIfscLookup } from "@/hooks/useIfscLookup";
import { useT } from "@/hooks/useI18n";

export interface StatutoryDraft {
  pan_number: string; aadhaar_number: string; name_as_per_aadhar: string; passport_number: string; passport_expiry: string;
  passport_issue_date: string; passport_place_of_issue: string; passport_country_of_issue: string;
  uan_number: string; esi_number: string; pf_covered: string; esi_covered: string;
  account_number: string; ifsc_code: string; bank_name: string; bank_branch_address: string; account_holder_name: string;
  account_type: string;
}

export const EMPTY_STATUTORY: StatutoryDraft = {
  pan_number: "", aadhaar_number: "", name_as_per_aadhar: "", passport_number: "", passport_expiry: "",
  passport_issue_date: "", passport_place_of_issue: "", passport_country_of_issue: "",
  uan_number: "", esi_number: "", pf_covered: "true", esi_covered: "false",
  account_number: "", ifsc_code: "", bank_name: "", bank_branch_address: "", account_holder_name: "",
  account_type: "savings",
};

function Toggle({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const t = useT();
  return (
    <div className="seg">
      {["true", "false"].map(v => (
        <button key={v} type="button" onClick={() => onChange(v)} aria-pressed={value === v}>
          {v === "true" ? t("Yes") : t("No")}
        </button>
      ))}
    </div>
  );
}

interface Props {
  value: StatutoryDraft;
  onChange: (v: StatutoryDraft) => void;
  documents: HireDocument[];
  uploading?: string | null;
  docError?: string;
  /** Pass both to upload the PAN / Aadhaar / passport files from this step (Edit full record does). Leave them out and this step shows
   *  only the numbers: the Hire wizard uploads every document once, on its Documents step, so nothing is asked for twice. */
  onUploadDoc?: (documentType: string, file: File) => void;
  onDeleteDoc?: (doc: HireDocument) => void;
  /** Messages for fields that failed the step's checks, by field key (the Hire wizard). */
  errors?: Record<string, string>;
  /** Edit full record only: the stored UAN, masked. The field itself stays write-only. */
  savedUanMasked?: string;
}

export default function StatutoryAccountsStep({ value, onChange, documents, uploading = null, docError = "", onUploadDoc, onDeleteDoc, errors = {}, savedUanMasked }: Props) {
  const t = useT();
  /** Marks a field's wrapper so the wizard can find it, and so it shows red while it has a message. */
  const mark = (field: string) => ({ className: "f hw-field", "data-hw-field": field, "data-hw-invalid": errors[field] ? ("true" as const) : undefined });
  // The newest form values. A change is merged into THESE, never into the `value` this render happened to receive: the IFSC lookup
  // answers seconds later (it calls an outside service), and a merge into the older `value` put the IFSC back to what it was
  // before its last character and wiped every field typed while the lookup was running (account holder, account number, PAN,
  // Aadhaar...). The ref is refreshed after every render, so it never lags what the parent holds, and updated at once by
  // each change, so two changes made in the same moment add up instead of the second erasing the first.
  const latest = useRef(value);
  useEffect(() => { latest.current = value; });
  function update(patch: Partial<StatutoryDraft>) {
    latest.current = { ...latest.current, ...patch };
    onChange(latest.current);
  }
  function set<K extends keyof StatutoryDraft>(key: K, v: StatutoryDraft[K]) {
    update({ [key]: v } as Partial<StatutoryDraft>);  // the computed key is exactly one StatutoryDraft key, so this is a valid patch
  }
  const docFor = (key: string) => documents.find(d => d.document_type === key);
  // The upload button, only on a screen that uploads from this step. Elsewhere nothing is shown.
  function renderDocSlot(documentType: string, label: string) {
    if (!onUploadDoc || !onDeleteDoc) return null;
    return (
      <div style={{ marginTop: 6 }}>
        <DocUploadButton documentType={documentType} label={t(label)} existing={docFor(documentType)}
          uploading={uploading === documentType} onUpload={onUploadDoc} onDelete={onDeleteDoc} />
      </div>
    );
  }

  const { lookup: lookupIfsc } = useIfscLookup();
  const latestIfscRef = useRef("");
  // Explicit feedback on every lookup outcome — this used to silently do
  // nothing when a valid-format IFSC code wasn't in the lookup dataset
  // (or the network call failed), leaving no way to tell "this code is
  // wrong" apart from "nothing happened yet" (reported live: a tester's
  // real HDFC code "wasn't accepted" with no error shown either way).
  const [ifscStatus, setIfscStatus] = useState<"idle" | "checking" | "found" | "not_found">("idle");
  function setIfsc(raw: string) {
    const normalized = raw.toUpperCase();
    set("ifsc_code", normalized);
    latestIfscRef.current = normalized;
    if (/^[A-Z]{4}0[A-Z0-9]{6}$/.test(normalized)) {
      setIfscStatus("checking");
      lookupIfsc(normalized).then(info => {
        if (latestIfscRef.current !== normalized) return;
        if (!info) { setIfscStatus("not_found"); return; }
        setIfscStatus("found");
        // Convenience auto-fill only: never clobber something the user already typed themselves (manually, or by editing a
        // previous auto-fill) into these two fields. "Already typed" is judged on the CURRENT values, not the ones from when the
        // lookup started, and both fields are saved in one change.
        const patch: Partial<StatutoryDraft> = {};
        if (info.bank && !latest.current.bank_name.trim()) patch.bank_name = info.bank;
        const branchAddress = [info.branch, info.address, info.city, info.state].filter(Boolean).join(", ");
        if (branchAddress && !latest.current.bank_branch_address.trim()) patch.bank_branch_address = branchAddress;
        if (Object.keys(patch).length > 0) update(patch);
      });
    } else {
      setIfscStatus("idle");
    }
  }

  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (docError) errorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [docError]);

  return (
    <div className="mstep on">
      <div className="note warn" style={{ marginBottom: 16 }}>
        <b>{t("Handled as sensitive data")}</b>
        {t("Government IDs and bank details are stored encrypted, masked in the UI by default, and every reveal is written to the audit log.")}
      </div>

      {docError && <div ref={errorRef} className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{docError}</div></div>}

      <div className="sechead">{t("GOVERNMENT IDS")}</div>
      <div className="g3">
        <div {...mark("pan_number")}>
          <label>{t("PAN")} <span className="req">*</span></label>
          <input value={value.pan_number} onChange={e => set("pan_number", e.target.value.toUpperCase())} placeholder="ABCDE1234F" maxLength={10} className="finput" />
          <FieldError message={errors.pan_number} />
          {renderDocSlot("pan_card", "PAN card")}
        </div>
        <div {...mark("aadhaar_number")}>
          <label>{t("Aadhaar")} <span className="req">*</span></label>
          <input value={value.aadhaar_number} onChange={e => set("aadhaar_number", e.target.value.replace(/\D/g, ""))} placeholder="123456789012" maxLength={12} className="finput" />
          <FieldError message={errors.aadhaar_number} />
          {renderDocSlot("aadhaar_card", "Aadhaar card")}
        </div>
        <div className="f">
          <label>{t("Name as per Aadhaar")}</label>
          <input value={value.name_as_per_aadhar} onChange={e => set("name_as_per_aadhar", e.target.value)} placeholder={t("As printed on the Aadhaar card")} className="finput" />
        </div>
        <div className="f">
          <label>{t("Passport")}</label>
          <input value={value.passport_number} onChange={e => set("passport_number", e.target.value)} placeholder={t("Optional")} className="finput" />
          {renderDocSlot("passport_photo", "passport")}
        </div>
        <div className="f">
          <label>{t("Passport issue date")}</label>
          <DateInput value={value.passport_issue_date} onChange={iso => set("passport_issue_date", iso)} disabled={!value.passport_number} className="finput" />
        </div>
        <div className="f">
          <label>{t("Passport expiry")}</label>
          <DateInput value={value.passport_expiry} onChange={iso => set("passport_expiry", iso)} disabled={!value.passport_number} className="finput" />
          {value.passport_issue_date && value.passport_expiry && value.passport_expiry <= value.passport_issue_date && (
            <div className="hint" style={{ color: "var(--error)" }}>{t("Expiry must be after the issue date.")}</div>
          )}
        </div>
        <div className="f">
          <label>{t("Place of issue")}</label>
          <input value={value.passport_place_of_issue} onChange={e => set("passport_place_of_issue", e.target.value)} placeholder={t("e.g. Hyderabad")} disabled={!value.passport_number} className="finput" />
        </div>
        <div className="f">
          <label>{t("Country of issue")}</label>
          <CountrySelect value={value.passport_country_of_issue} onChange={v => set("passport_country_of_issue", v)}
            mode="name" placeholder={t("Select country")} />
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">{t("PROVIDENT FUND")}</div>
      <div className="togline" style={{ marginBottom: 14 }}>
        <span>{t("Covered under PF")}</span>
        <Toggle value={value.pf_covered} onChange={v => set("pf_covered", v)} />
      </div>
      <div className="g3">
        <div className="f">
          <label>{t("UAN")}</label>
          <input value={value.uan_number} onChange={e => set("uan_number", e.target.value.replace(/\D/g, ""))} placeholder={t("12 digits, if available")} maxLength={12} className="finput" />
          {value.uan_number && value.uan_number.length !== 12 ? (
            <div className="hint" style={{ color: "var(--error)" }}>{t("UAN must be 12 digits")}</div>
          ) : (
            <div className="hint">
              {savedUanMasked
                ? t("On file: {masked}. Leave blank to keep it, or type a new 12-digit UAN to replace it.", { masked: savedUanMasked })
                : t("Leave blank for a first job — EPFO will allot one.")}
            </div>
          )}
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">{t("ESI")}</div>
      <div className="togline" style={{ marginBottom: 14 }}>
        <span>{t("Covered under ESI")}</span>
        <Toggle value={value.esi_covered} onChange={v => set("esi_covered", v)} />
      </div>
      {value.esi_covered === "true" && (
        <div className="g3">
          <div className="f">
            <label>{t("ESI number")}</label>
            <input value={value.esi_number} onChange={e => set("esi_number", e.target.value.replace(/\D/g, ""))} placeholder={t("10 digits, if available")} maxLength={10} className="finput" />
          </div>
        </div>
      )}

      <div className="divider" />
      <div className="sechead">{t("BANK ACCOUNT")}</div>
      <div className="g3">
        <div {...mark("account_holder_name")}>
          <label>{t("Account holder name")} <span className="req">*</span></label>
          <input value={value.account_holder_name} onChange={e => set("account_holder_name", e.target.value)} placeholder={t("Should match the PAN name")} className="finput" />
          <FieldError message={errors.account_holder_name} />
        </div>
        <div {...mark("account_number")}>
          <label>{t("Account number")} <span className="req">*</span></label>
          <input value={value.account_number} onChange={e => set("account_number", e.target.value.replace(/\D/g, ""))} className="finput" />
          <FieldError message={errors.account_number} />
        </div>
        <div className="f">
          <label>{t("Account type")}</label>
          <select value={value.account_type} onChange={e => set("account_type", e.target.value)} className="finput">
            <option value="savings">{t("Savings")}</option>
            <option value="current">{t("Current")}</option>
          </select>
        </div>
        <div {...mark("ifsc_code")}>
          <label>{t("IFSC code")} <span className="req">*</span></label>
          <input value={value.ifsc_code} onChange={e => setIfsc(e.target.value)} placeholder="HDFC0001234" maxLength={11} className="finput" />
          <FieldError message={errors.ifsc_code} />
          {ifscStatus === "checking" && <div className="hint">{t("Looking up bank…")}</div>}
          {ifscStatus === "found" && <div className="hint" style={{ color: "var(--success, #16a34a)" }}>{t("Bank and branch found — filled in below.")}</div>}
          {ifscStatus === "not_found" && (
            // Deliberately NOT var(--error)/red — a valid-format code that
            // just isn't in this lookup dataset used to render identically
            // to an actually-malformed code, which testers read as "the
            // system is rejecting this IFSC". The code itself is still
            // accepted here regardless (setIfsc always saves it, and the
            // real format check on Next only checks the pattern, not
            // whether this lookup found a match) — only the convenience
            // auto-fill didn't have data for this specific branch.
            <div className="hint" style={{ color: "var(--warn, #b45309)" }}>
              {t("Couldn't auto-fill bank details for this code — it's still accepted, just enter the bank name/branch manually below.")}
            </div>
          )}
        </div>
        <div className="f">
          <label>{t("Bank name")}</label>
          <input value={value.bank_name} onChange={e => set("bank_name", e.target.value)} placeholder={t("e.g. HDFC Bank")} className="finput" />
        </div>
        <div className="f">
          <label>{t("Branch / address")}</label>
          <input value={value.bank_branch_address} onChange={e => set("bank_branch_address", e.target.value)} placeholder={t("Auto-filled from IFSC, or enter manually")} className="finput" />
        </div>
      </div>
    </div>
  );
}
