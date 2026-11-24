"use client";

// Office settings: whether the Company Code is in use, and the two flags (headquarter, metro city).

import { useT } from "@/hooks/useI18n";
import type { BranchForm } from "./_data";
import { ChoiceCard, FormSection, StatusSwitch } from "./BranchFormUi";
import { SECTION_COPY } from "./branchFormCopy";

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
}

export default function BranchSettingsSection({ form, onChange }: Props) {
  const t = useT();
  return (
    <FormSection id="bf-settings" title={t(SECTION_COPY.settings.title)} subtitle={t(SECTION_COPY.settings.hint)}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{t("Status")}</span>
        <StatusSwitch value={form.status} onChange={status => onChange({ status })} />
        {form.status === "inactive" && <span style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{t("Not offered for new hires.")}</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}>
        <ChoiceCard
          checked={form.is_headquarter} onChange={checked => onChange({ is_headquarter: checked })} icon="ti-flag-3"
          title={t("Mark as Headquarter")} description={t("The main office. Only one office can be the headquarter.")}
        />
        <ChoiceCard
          checked={form.is_metro} onChange={checked => onChange({ is_metro: checked })} icon="ti-building-community"
          title={t("Metro City (HRA)")} description={t("Pay HRA at 50% of Basic instead of 40%.")}
        />
      </div>
    </FormSection>
  );
}
