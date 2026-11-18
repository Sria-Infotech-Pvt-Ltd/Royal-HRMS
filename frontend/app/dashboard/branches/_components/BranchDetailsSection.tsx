"use client";

// Details section of the Company Code form: the generated code, the name and the address.

import type { BranchForm } from "./_data";
import { Field, FormSection } from "./BranchFormUi";
import { SECTION_COPY } from "./branchFormCopy";

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
  clearErrors: (...keys: string[]) => void;
  errors: Record<string, string>;
  codeLoading: boolean;
}

export default function BranchDetailsSection({ form, onChange, clearErrors, errors, codeLoading }: Props) {
  return (
    <FormSection id="bf-details" title={SECTION_COPY.details.title} subtitle={SECTION_COPY.details.hint}>
      <div className="form-row cols-2">
        <Field
          label="Company Code" error={errors.branch_code} htmlFor="bf-code"
          hint={form.branch_code && !codeLoading ? "Made from the city. You cannot change it." : "Made from the city you chose."}
        >
          <div style={{ position: "relative" }}>
            <input
              id="bf-code" type="text" readOnly value={codeLoading ? "" : form.branch_code} aria-label="Company Code"
              className={`field-input${errors.branch_code ? " field-error" : ""}`}
              placeholder={!form.city ? "Select a city first" : codeLoading ? "Generating…" : ""}
              style={{ background: "var(--bg-low)", cursor: "default", fontFamily: "monospace", fontWeight: 700, letterSpacing: ".06em", paddingRight: codeLoading ? 36 : undefined }}
            />
            {codeLoading && <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--outline)" }}><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /></span>}
          </div>
        </Field>
        <Field label="Company Code Name" required error={errors.branch_name} htmlFor="bf-name">
          <input
            id="bf-name" type="text" className={`field-input${errors.branch_name ? " field-error" : ""}`} value={form.branch_name} placeholder="e.g. Bengaluru HQ" maxLength={200}
            onChange={event => { clearErrors("branch_name"); onChange({ branch_name: event.target.value.replace(/[^A-Za-z0-9 &.-]/g, "") }); }}
          />
        </Field>
      </div>

      <Field label="Address" required error={errors.address} htmlFor="bf-address" hint="Street, area and PIN code.">
        <textarea
          id="bf-address" rows={3} className={`field-input${errors.address ? " field-error" : ""}`} value={form.address} placeholder="Full Company Code address"
          onChange={event => { clearErrors("address"); onChange({ address: event.target.value }); }}
        />
      </Field>
    </FormSection>
  );
}
