"use client";

// Current/permanent address section for Hire wizard Step 1 — replaces the
// shared onboarding DynamicStepFields rendering for these specific keys so
// the exact reference layout (Landmark/City/District row, State/Pincode/
// Country row, explicit "+Suggest" buttons, Yes/No toggle) can be built
// without changing that shared component's behavior for its other callers.
//
// "+Suggest" on City/District/State all resolve the same real PIN-code
// lookup already used elsewhere in this app (apps.accounts.views_pincode) —
// District/State come from that dataset's own district/state fields; City
// comes from the same dataset's post-office name (e.g. "Cyberabad S.O" ->
// "Cyberabad") with the postal office-type suffix stripped server-side —
// a real locality name for that PIN code, not a guess.

import { useState } from "react";
import { usePincodeLookup } from "@/hooks/usePincodeLookup";
import { StateSelect, DistrictSelect } from "@/components/StateDistrictSelect";
import type { ProfileForm } from "@/app/onboarding/_types";

export type AddressFormFields = Pick<
  ProfileForm,
  | "current_address" | "current_address_line2" | "current_village" | "current_district" | "current_state" | "current_pin_code"
  | "permanent_address" | "permanent_address_line2" | "permanent_village" | "permanent_district" | "permanent_state" | "permanent_pin_code"
  | "permanent_same_as_current"
>;

export interface AddressExtras {
  landmark: string;
  country: string;
}

export const EMPTY_ADDRESS_EXTRAS: AddressExtras = { landmark: "", country: "India" };

interface Props {
  form: AddressFormFields;
  extras: AddressExtras;
  onFieldChange: (key: keyof AddressFormFields, value: string) => void;
  onExtrasChange: (key: keyof AddressExtras, value: string) => void;
}

function SuggestButton({ onClick, disabled, loading }: { onClick: () => void; disabled: boolean; loading: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      title={disabled ? "Enter a 6-digit PIN code first" : "Suggest from PIN code"} className="sugbtn"
      style={{ opacity: disabled ? 0.5 : 1, cursor: disabled ? "not-allowed" : "pointer" }}>
      {loading ? "…" : "+ Suggest"}
    </button>
  );
}

export default function AddressFields({ form, extras, onFieldChange, onExtrasChange }: Props) {
  const { lookup } = usePincodeLookup();
  const [suggesting, setSuggesting] = useState<"village" | "district" | "state" | null>(null);
  const pincodeReady = /^\d{6}$/.test(form.current_pin_code);

  async function suggest(field: "village" | "district" | "state") {
    if (!pincodeReady) return;
    setSuggesting(field);
    const loc = await lookup(form.current_pin_code);
    setSuggesting(null);
    if (!loc) return;
    if (field === "village" && loc.locality) onFieldChange("current_village", loc.locality);
    if (field === "district" && loc.district) onFieldChange("current_district", loc.district);
    if (field === "state" && loc.state) onFieldChange("current_state", loc.state);
  }

  const sameAsCurrent = form.permanent_same_as_current === "true";

  return (
    <div>
      <div className="sechead">CURRENT ADDRESS</div>
      <div className="g2" style={{ marginBottom: 10 }}>
        <div className="f">
          <label>Address line 1</label>
          <input value={form.current_address} onChange={e => onFieldChange("current_address", e.target.value)}
            placeholder="Flat / house no., building" className="finput" />
        </div>
        <div className="f">
          <label>Address line 2</label>
          <input value={form.current_address_line2} onChange={e => onFieldChange("current_address_line2", e.target.value)}
            placeholder="Street, area" className="finput" />
        </div>
      </div>

      <div className="g3" style={{ marginBottom: 10 }}>
        <div className="f">
          <label>Landmark <span className="tag">OPTIONAL</span></label>
          <input value={extras.landmark} onChange={e => onExtrasChange("landmark", e.target.value)} placeholder="Optional" className="finput" />
        </div>
        <div className="f">
          <label>City</label>
          <div className="flex gap-2">
            <input value={form.current_village} onChange={e => onFieldChange("current_village", e.target.value)} className="finput" />
            <SuggestButton onClick={() => suggest("village")} disabled={!pincodeReady} loading={suggesting === "village"} />
          </div>
        </div>
        <div className="f">
          <label>District</label>
          <div className="flex gap-2">
            <DistrictSelect value={form.current_district} state={form.current_state} onChange={v => onFieldChange("current_district", v)} inputClassName="finput" />
            <SuggestButton onClick={() => suggest("district")} disabled={!pincodeReady} loading={suggesting === "district"} />
          </div>
        </div>
      </div>

      <div className="g3" style={{ marginBottom: 14 }}>
        <div className="f">
          <label>State</label>
          <div className="flex gap-2">
            <StateSelect value={form.current_state} onChange={v => { onFieldChange("current_state", v); onFieldChange("current_district", ""); }} inputClassName="finput" />
            <SuggestButton onClick={() => suggest("state")} disabled={!pincodeReady} loading={suggesting === "state"} />
          </div>
        </div>
        <div className="f">
          <label>Pincode</label>
          <input value={form.current_pin_code} onChange={e => onFieldChange("current_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="500081" maxLength={6} inputMode="numeric" className="finput" />
        </div>
        <div className="f">
          <label>Country</label>
          <input value={extras.country} onChange={e => onExtrasChange("country", e.target.value)} placeholder="India" className="finput" />
        </div>
      </div>

      <div className="togline" style={{ marginBottom: 16 }}>
        <span>Permanent address is the same as current</span>
        <div className="seg">
          {["true", "false"].map(v => (
            <button key={v} type="button" onClick={() => onFieldChange("permanent_same_as_current", v)}
              aria-pressed={form.permanent_same_as_current === v}>
              {v === "true" ? "Yes" : "No"}
            </button>
          ))}
        </div>
      </div>

      {!sameAsCurrent && (
        <>
          <div className="sechead">PERMANENT ADDRESS</div>
          <div className="g2" style={{ marginBottom: 10 }}>
            <div className="f">
              <label>Address line 1</label>
              <input value={form.permanent_address} onChange={e => onFieldChange("permanent_address", e.target.value)}
                placeholder="Flat / house no., building" className="finput" />
            </div>
            <div className="f">
              <label>Address line 2</label>
              <input value={form.permanent_address_line2} onChange={e => onFieldChange("permanent_address_line2", e.target.value)}
                placeholder="Street, area" className="finput" />
            </div>
          </div>
          <div className="g3" style={{ marginBottom: 14 }}>
            <div className="f">
              <label>City</label>
              <input value={form.permanent_village} onChange={e => onFieldChange("permanent_village", e.target.value)} className="finput" />
            </div>
            <div className="f">
              <label>District</label>
              <DistrictSelect value={form.permanent_district} state={form.permanent_state} onChange={v => onFieldChange("permanent_district", v)} inputClassName="finput" />
            </div>
            <div className="f">
              <label>State</label>
              <StateSelect value={form.permanent_state} onChange={v => { onFieldChange("permanent_state", v); onFieldChange("permanent_district", ""); }} inputClassName="finput" />
            </div>
          </div>
          <div className="g3" style={{ marginBottom: 14 }}>
            <div className="f">
              <label>Pincode</label>
              <input value={form.permanent_pin_code} onChange={e => onFieldChange("permanent_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                maxLength={6} inputMode="numeric" className="finput" />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
