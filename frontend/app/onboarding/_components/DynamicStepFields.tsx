"use client";

import DynamicField from "@/components/OnboardingDynamicField";
import CustomFieldFileUpload from "@/components/CustomFieldFileUpload";
import type { CustomFieldFileValue, OnboardingFieldConfig } from "@/types/onboardingFieldConfig";
import type { ProfileForm } from "../_types";

interface Props {
  configs: OnboardingFieldConfig[]; // already filtered to one step, sorted by order
  form: ProfileForm;
  customValues: Record<string, string>;
  onBuiltinChange: (fieldKey: keyof ProfileForm, value: string) => void;
  onCustomChange: (fieldKey: string, value: string) => void;
  customFileValues: CustomFieldFileValue[];
  uploadingFileKey: string | null;
  fileUploadError: string | null;
  onCustomFileUpload: (fieldKey: string, file: File) => void;
  onCustomFileDelete: (fieldKey: string, valueId: number) => void;
}

// checkbox/dropdown/date/number/text render compactly in the auto-fit grid;
// textarea and file fields get their own full-width row — textarea because
// long text always has, file because CustomFieldFileUpload's card UI doesn't
// fit the compact grid cells the way a plain input does.
export default function DynamicStepFields({
  configs, form, customValues, onBuiltinChange, onCustomChange,
  customFileValues, uploadingFileKey, fileUploadError, onCustomFileUpload, onCustomFileDelete,
}: Props) {
  const shortFields = configs.filter(c => c.field_type !== "textarea" && c.field_type !== "file");
  const longFields = configs.filter(c => c.field_type === "textarea");
  const fileFields = configs.filter(c => c.field_type === "file");

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
      {fileFields.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 14 }}>
          {fileUploadError && <div className="alert alert-error">{fileUploadError}</div>}
          {fileFields.map(config => (
            <CustomFieldFileUpload
              key={config.field_key}
              fieldKey={config.field_key}
              label={config.label}
              required={config.required}
              allowMultiple={config.allow_multiple}
              value={customFileValues.filter(v => v.field_key === config.field_key)}
              uploading={uploadingFileKey === config.field_key}
              onUpload={onCustomFileUpload}
              onDelete={onCustomFileDelete}
            />
          ))}
        </div>
      )}
      {configs.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem" }}>
          No fields are configured for this step.
        </p>
      )}
    </div>
  );
}
