"use client";

import { useRef } from "react";
import DynamicField from "@/components/OnboardingDynamicField";
import CustomFieldFileUpload from "@/components/CustomFieldFileUpload";
import { usePincodeLookup } from "@/hooks/usePincodeLookup";
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

// checkbox/dropdown/date/number/text render compactly, grouped into
// contiguous grid rows; textarea and file fields each get their own
// full-width row — textarea because long text always needs it, file because
// CustomFieldFileUpload's card UI doesn't fit the compact grid cells the way
// a plain input does. Fields render in the exact order `configs` is already
// sorted in (by each field's configured `order`) — grid rows are just
// contiguous *runs* of short fields within that sequence, not a single
// "all short fields, then all textareas" bucket. That distinction matters
// for e.g. Current Address (a short textarea, holding just the house/street
// line) sitting right next to its own Village/District/State/PIN Code
// fields — bucketing would separate them by yanking the textarea down past
// every short field in the step, regardless of where it's actually
// configured.
type Run =
  | { kind: "grid"; items: OnboardingFieldConfig[] }
  | { kind: "full"; item: OnboardingFieldConfig }
  | { kind: "addressPair"; line1: OnboardingFieldConfig; line2: OnboardingFieldConfig };

// Permanent address's own field_keys — used to (a) find where to inject the
// "same as current" checkbox (right before the first run made up of these)
// and (b) hide every run made up of these once it's checked, so the common
// case (permanent == current) doesn't ask for the same district/state/PIN
// twice. Matched by field_key rather than assumed-contiguous position so
// this stays correct even if HR has reordered fields in Settings.
const PERMANENT_FIELD_KEYS = new Set([
  "permanent_address", "permanent_address_line2", "permanent_village",
  "permanent_district", "permanent_state", "permanent_pin_code",
]);
const CURRENT_FIELD_KEYS = new Set([
  "current_address", "current_address_line2", "current_village",
  "current_district", "current_state", "current_pin_code",
]);

// Aadhaar/disability/international-worker/passport fields are seeded right
// after permanent_pin_code (see migration 0150) but are their own logical
// group, not part of the address block — without a heading of their own
// they render directly under "Permanent Address" with nothing to signal the
// section changed, making them look like address fields.
const IDENTITY_DECLARATION_FIELD_KEYS = new Set([
  "aadhaar_number", "is_disabled", "disability_type", "disability_percentage",
  "disability_certificate_number", "is_international_worker",
  "international_worker_country", "passport_number", "passport_expiry",
]);

// Address Line 1 -> its own Address Line 2's field_key — when the two sit
// immediately next to each other in `configs` (their default seeded order),
// buildRuns pairs them into one half-width row instead of Line 1 getting a
// full-width row to itself the way a real multi-line address blob would
// need. Falls back to Line 1 alone if HR has hidden or moved Line 2 in
// Settings (matches PERMANENT_FIELD_KEYS' own "matched by key, not assumed
// position" tolerance).
const ADDRESS_LINE2_KEY: Record<string, string> = {
  current_address: "current_address_line2",
  permanent_address: "permanent_address_line2",
};

function isPermanentRun(run: Run): boolean {
  if (run.kind === "grid") return run.items.every(c => PERMANENT_FIELD_KEYS.has(c.field_key));
  if (run.kind === "addressPair") return PERMANENT_FIELD_KEYS.has(run.line1.field_key);
  return PERMANENT_FIELD_KEYS.has(run.item.field_key);
}

function isCurrentRun(run: Run): boolean {
  if (run.kind === "grid") return run.items.every(c => CURRENT_FIELD_KEYS.has(c.field_key));
  if (run.kind === "addressPair") return CURRENT_FIELD_KEYS.has(run.line1.field_key);
  return CURRENT_FIELD_KEYS.has(run.item.field_key);
}

function isIdentityDeclarationRun(run: Run): boolean {
  if (run.kind === "grid") return run.items.every(c => IDENTITY_DECLARATION_FIELD_KEYS.has(c.field_key));
  if (run.kind === "addressPair") return IDENTITY_DECLARATION_FIELD_KEYS.has(run.line1.field_key);
  return IDENTITY_DECLARATION_FIELD_KEYS.has(run.item.field_key);
}

// PIN code field_key -> the address prefix ("current"/"permanent") whose
// District/State fields get auto-filled once a valid 6-digit value lands
// here — see usePincodeLookup.
const PIN_CODE_TO_PREFIX: Record<string, string> = {
  current_pin_code: "current",
  permanent_pin_code: "permanent",
};

function buildRuns(configs: OnboardingFieldConfig[]): Run[] {
  const runs: Run[] = [];
  for (let i = 0; i < configs.length; i++) {
    const config = configs[i];
    if (config.field_type === "textarea" || config.field_type === "file") {
      const line2Key = ADDRESS_LINE2_KEY[config.field_key];
      const next = configs[i + 1];
      if (line2Key && next && next.field_key === line2Key) {
        runs.push({ kind: "addressPair", line1: config, line2: next });
        i++; // consumed next as line2 — don't visit it again
        continue;
      }
      runs.push({ kind: "full", item: config });
      continue;
    }
    const last = runs[runs.length - 1];
    if (last && last.kind === "grid") last.items.push(config);
    else runs.push({ kind: "grid", items: [config] });
  }
  return runs;
}

export default function DynamicStepFields({
  configs, form, customValues, onBuiltinChange, onCustomChange,
  customFileValues, uploadingFileKey, fileUploadError, onCustomFileUpload, onCustomFileDelete,
}: Props) {
  function valueFor(config: OnboardingFieldConfig): string {
    if (config.is_custom) return customValues[config.field_key] ?? "";
    return (form as unknown as Record<string, string>)[config.field_key] ?? "";
  }

  // current_district/permanent_district need their paired State's current
  // value to filter the district list (StateDistrictSelect.tsx) — read
  // directly off `form` rather than looking up another config, since
  // current_state/permanent_state are always plain ProfileForm keys.
  const DISTRICT_TO_STATE_KEY: Record<string, keyof ProfileForm> = {
    current_district: "current_state",
    permanent_district: "permanent_state",
  };
  function pairedStateFor(config: OnboardingFieldConfig): string | undefined {
    const stateKey = DISTRICT_TO_STATE_KEY[config.field_key];
    return stateKey ? form[stateKey] : undefined;
  }

  const { lookup: lookupPincode } = usePincodeLookup();
  // Tracks the most recent PIN code value typed per address prefix, so that
  // if a lookup response for an older value arrives after the user has
  // already typed a different PIN code (a real race — e.g. correcting a
  // typo quickly), it gets discarded instead of overwriting District/State
  // with stale data for a PIN code that's no longer in the field.
  const latestPincodeRef = useRef<Record<string, string>>({});

  function onChangeFor(config: OnboardingFieldConfig) {
    return (value: string) => {
      if (config.is_custom) { onCustomChange(config.field_key, value); return; }
      onBuiltinChange(config.field_key as keyof ProfileForm, value);

      // Picking a different State invalidates whatever District was
      // selected under the previous one (StateDistrictSelect.tsx's own
      // caller-responsibility note) — clear it here rather than leaving a
      // stale district silently paired with a new state.
      const STATE_TO_DISTRICT_KEY: Record<string, keyof ProfileForm> = {
        current_state: 'current_district', permanent_state: 'permanent_district',
      };
      const districtKey = STATE_TO_DISTRICT_KEY[config.field_key];
      if (districtKey) onBuiltinChange(districtKey, '');

      const prefix = PIN_CODE_TO_PREFIX[config.field_key];
      if (prefix) {
        latestPincodeRef.current[prefix] = value;
        if (/^\d{6}$/.test(value)) {
          lookupPincode(value).then(loc => {
            if (!loc) return;
            if (latestPincodeRef.current[prefix] !== value) return; // superseded by a newer edit
            if (loc.district) onBuiltinChange(`${prefix}_district` as keyof ProfileForm, loc.district);
            if (loc.state) onBuiltinChange(`${prefix}_state` as keyof ProfileForm, loc.state);
          });
        }
      }
    };
  }

  const runs = buildRuns(configs);
  const hasFileField = configs.some(c => c.field_type === "file");

  // Only meaningful when this step actually has permanent-address fields
  // configured (i.e. step 0) — every other step's runs.every(isPermanentRun)
  // check on an empty/unrelated set just comes back false, so this whole
  // block is a no-op there.
  const firstPermanentRunIndex = runs.findIndex(isPermanentRun);
  const hasPermanentFields = firstPermanentRunIndex !== -1;
  const firstCurrentRunIndex = runs.findIndex(isCurrentRun);
  const hasCurrentFields = firstCurrentRunIndex !== -1;
  const firstIdentityRunIndex = runs.findIndex(isIdentityDeclarationRun);
  const hasIdentityFields = firstIdentityRunIndex !== -1;
  const sameAsCurrent = (form as unknown as Record<string, string>).permanent_same_as_current === "true";

  const sectionHeading = (text: string) => (
    <h4
      key={`heading-${text}`}
      style={{
        display: "flex", alignItems: "center", gap: 8,
        fontSize: ".8rem", fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase",
        color: "var(--on-variant)", margin: "22px 0 10px",
        paddingBottom: 8, borderBottom: "1px solid var(--outline-v)",
      }}
    >
      <span style={{ width: 4, height: 14, borderRadius: 2, background: "var(--primary)", flexShrink: 0 }} />
      {text}
    </h4>
  );

  return (
    <div>
      {hasFileField && fileUploadError && (
        <div className="alert alert-error" style={{ marginBottom: 14 }}>{fileUploadError}</div>
      )}
      {runs.map((run, i) => {
        const heading = hasCurrentFields && i === firstCurrentRunIndex
          ? sectionHeading("Current Address")
          : hasPermanentFields && i === firstPermanentRunIndex
          ? sectionHeading("Permanent Address")
          : hasIdentityFields && i === firstIdentityRunIndex
          ? sectionHeading("Identity & Declarations")
          : null;
        const toggle = hasPermanentFields && i === firstPermanentRunIndex && (
          <label key="permanent-same-as-current" className="module-check" style={{ margin: "4px 0 12px" }}>
            <input
              type="checkbox"
              checked={sameAsCurrent}
              onChange={e => onBuiltinChange("permanent_same_as_current", e.target.checked ? "true" : "false")}
            />
            <span>Permanent address is the same as current address</span>
          </label>
        );
        if (isPermanentRun(run) && sameAsCurrent) return (<div key={`wrap-${i}`}>{heading}{toggle}</div>);

        if (run.kind === "grid") {
          return (
            <div key={`wrap-grid-${i}`}>
              {heading}
              {toggle}
              <div className="field-group-row">
                {run.items.map(config => (
                  <DynamicField key={config.field_key} config={config} value={valueFor(config)} onChange={onChangeFor(config)} pairedState={pairedStateFor(config)} />
                ))}
              </div>
            </div>
          );
        }
        if (run.kind === "addressPair") {
          return (
            <div key={`wrap-addr-${i}`}>
              {heading}
              {toggle}
              <div className="field-group-row" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <DynamicField config={run.line1} value={valueFor(run.line1)} onChange={onChangeFor(run.line1)} pairedState={pairedStateFor(run.line1)} />
                <DynamicField config={run.line2} value={valueFor(run.line2)} onChange={onChangeFor(run.line2)} pairedState={pairedStateFor(run.line2)} />
              </div>
            </div>
          );
        }
        if (run.item.field_type === "file") {
          return (
            <div key={`wrap-${run.item.field_key}`}>
              {heading}
              {toggle}
              <div style={{ marginTop: 14 }}>
                <CustomFieldFileUpload
                  fieldKey={run.item.field_key}
                  label={run.item.label}
                  required={run.item.required}
                  allowMultiple={run.item.allow_multiple}
                  value={customFileValues.filter(v => v.field_key === run.item.field_key)}
                  uploading={uploadingFileKey === run.item.field_key}
                  onUpload={onCustomFileUpload}
                  onDelete={onCustomFileDelete}
                />
              </div>
            </div>
          );
        }
        return (
          <div key={`wrap-${run.item.field_key}`}>
            {heading}
            {toggle}
            <DynamicField config={run.item} value={valueFor(run.item)} onChange={onChangeFor(run.item)} pairedState={pairedStateFor(run.item)} />
          </div>
        );
      })}
      {configs.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem" }}>
          No fields are configured for this step.
        </p>
      )}
    </div>
  );
}
