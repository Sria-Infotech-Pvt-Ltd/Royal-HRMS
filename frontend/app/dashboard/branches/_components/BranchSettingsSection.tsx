"use client";

// Office settings: whether the Company Code is in use, and the two flags (headquarter, metro city).

import type { BranchForm } from "./_data";
import { ChoiceCard, FormSection, StatusSwitch } from "./BranchFormUi";
import { SECTION_COPY } from "./branchFormCopy";

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
}

export default function BranchSettingsSection({ form, onChange }: Props) {
  return (
    <FormSection id="bf-settings" title={SECTION_COPY.settings.title} subtitle={SECTION_COPY.settings.hint}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>Status</span>
        <StatusSwitch value={form.status} onChange={status => onChange({ status })} />
        {form.status === "inactive" && <span style={{ fontSize: 11.5, color: "var(--on-variant)" }}>Not offered for new hires.</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}>
        <ChoiceCard
          checked={form.is_headquarter} onChange={checked => onChange({ is_headquarter: checked })} icon="ti-flag-3"
          title="Mark as Headquarter" description="The main office. Only one office can be the headquarter."
        />
        <ChoiceCard
          checked={form.is_metro} onChange={checked => onChange({ is_metro: checked })} icon="ti-building-community"
          title="Metro City (HRA)" description="Pay HRA at 50% of Basic instead of 40%."
        />
      </div>
    </FormSection>
  );
}
