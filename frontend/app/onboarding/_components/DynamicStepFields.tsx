"use client";

import DynamicField from "@/components/OnboardingDynamicField";
import type { OnboardingFieldConfig } from "@/types/onboardingFieldConfig";
import type { ProfileForm } from "../_types";

interface Props {
  configs: OnboardingFieldConfig[]; // already filtered to one step, sorted by order
  form: ProfileForm;
  customValues: Record<string, string>;
  onBuiltinChange: (fieldKey: keyof ProfileForm, value: string) => void;
  onCustomChange: (fieldKey: string, value: string) => void;
}

// checkbox/dropdown/date/number/text render compactly in the auto-fit grid;
// textarea fields get their own full-width row, matching how this wizard's
// original hand-written steps always gave long-text fields the full width.
export default function DynamicStepFields({ configs, form, customValues, onBuiltinChange, onCustomChange }: Props) {
  const shortFields = configs.filter(c => c.field_type !== "textarea");
  const longFields = configs.filter(c => c.field_type === "textarea");

  function valueFor(config: OnboardingFieldConfig): string {
    if (config.is_custom) return customValues[config.field_key] ?? "";
    return (form as unknown as Record<string, string>)[config.field_key] ?? "";
  }

  function onChangeFor(config: OnboardingFieldConfig) {
    return (value: string) => {
      if (config.is_custom) onCustomChange(config.field_key, value);
      else onBuiltinChange(config.field_key as keyof ProfileForm, value);
    };
  }

  return (
    <div>
      {shortFields.length > 0 && (
        <div className="field-group-row">
          {shortFields.map(config => (
            <DynamicField key={config.field_key} config={config} value={valueFor(config)} onChange={onChangeFor(config)} />
          ))}
        </div>
      )}
      {longFields.map(config => (
        <DynamicField key={config.field_key} config={config} value={valueFor(config)} onChange={onChangeFor(config)} />
      ))}
      {configs.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem" }}>
          No fields are configured for this step.
        </p>
      )}
    </div>
  );
}
