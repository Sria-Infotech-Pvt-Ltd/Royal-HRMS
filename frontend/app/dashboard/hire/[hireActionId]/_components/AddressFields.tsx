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

import { useEffect, useRef, useState } from "react";
import { usePincodeLookup, type PincodeLocation } from "@/hooks/usePincodeLookup";
import { usePincodesInDistrict } from "@/hooks/usePincodesInDistrict";
import PincodeSelect from "@/components/PincodeSelect";
import CountrySelect from "@/components/CountrySelect";
import { StateSelect, DistrictSelect } from "@/components/StateDistrictSelect";
import { INDIA_STATE_NAMES, canonicalName, closestName, districtsForState } from "@/lib/indiaStatesDistricts";
import type { ProfileForm } from "@/app/onboarding/_types";

export type AddressFormFields = Pick<
  ProfileForm,
  | "current_address" | "current_address_line2" | "current_village" | "current_district" | "current_state" | "current_pin_code"
  | "permanent_address" | "permanent_address_line2" | "permanent_village" | "permanent_district" | "permanent_state" | "permanent_pin_code"
  | "permanent_same_as_current"
>;

// Landmark and country have no column of their own: like the present address's, they live in the draft, for both addresses.
export interface AddressExtras {
  landmark: string;
  country: string;
  permanent_landmark: string;
  permanent_country: string;
}

export const EMPTY_ADDRESS_EXTRAS: AddressExtras = { landmark: "", country: "India", permanent_landmark: "", permanent_country: "India" };

interface Props {
  form: AddressFormFields;
  extras: AddressExtras;
  onFieldChange: (key: keyof AddressFormFields, value: string) => void;
  onExtrasChange: (key: keyof AddressExtras, value: string) => void;
}

function SuggestButton({ onClick, isWaiting, isDone, isLoading }: { onClick: () => void; isWaiting: boolean; isDone: boolean; isLoading: boolean }) {
  // Deliberately NOT the native `disabled` attribute: browsers grey a real disabled button out whatever the CSS says, and a dead button
  // gives no reason. Three looks: no PIN code yet (faded, and a click says why), already filled from the PIN code (a green tick: nothing
  // left to suggest, and a click just applies it again), and ready (bright).
  const state = isWaiting ? " is-waiting" : isDone ? " is-done" : "";
  const title = isWaiting ? "Needs a 6-digit PIN code" : isDone ? "Already filled in from the PIN code" : "Fill this in from the PIN code";
  return (
    <button type="button" onClick={onClick} className={`hw-suggest${state}`} aria-busy={isLoading} title={title}>
      {isLoading ? <i className="ti ti-loader-2 spin" /> : isDone ? <><i className="ti ti-circle-check" /> Filled</> : <><i className="ti ti-wand" /> Suggest</>}
    </button>
  );
}

type Prefix = "current" | "permanent";
type SuggestField = "village" | "state" | "district";

interface PlaceFromPincode { pincode: string; state: string; district: string; locality: string }

/**
 * The PIN-code helpers of one address, all reading the same PIN code:
 *  - As soon as the 6 digits are in, the state, district and city that are still EMPTY are filled in from it. Anything already typed
 *    or chosen is left alone.
 *  - The Suggest buttons do the same on request, and replace what is there. City gets the area the PIN code serves. State and District
 *    are a pair, so either button fills both (a district on its own would sit in a District box that stays locked until a state is
 *    chosen, and look as if nothing happened). Names are written the way this form lists them.
 *  - A button shows "Filled" when its field already holds what the PIN code says, so a lit button always means there is something to do.
 * With no PIN code, or an unknown one, a button says so under the row.
 */
function useAddressSuggest(prefix: Prefix, form: AddressFormFields, onFieldChange: Props["onFieldChange"]) {
  const { lookup } = usePincodeLookup();
  const [suggesting, setSuggesting] = useState<SuggestField | null>(null);
  const [note, setNote] = useState("");
  // What the PIN code said, with the PIN code it was said for, so an answer for an older PIN code is never used for a newer one.
  const [place, setPlace] = useState<PlaceFromPincode | null>(null);
  const pincode = form[`${prefix}_pin_code`];
  const isPincodeReady = /^\d{6}$/.test(pincode);

  // The newest form and handler, for the answer that arrives later (they change on every keystroke).
  const latest = useRef({ form, onFieldChange });
  useEffect(() => { latest.current = { form, onFieldChange }; });

  const settle = (found: PincodeLocation): PlaceFromPincode => {
    const state = canonicalName(INDIA_STATE_NAMES, found.state) ?? found.state;
    return { pincode, state, district: closestName(districtsForState(state), found.district) ?? found.district, locality: found.locality };
  };

  // Complete PIN code: look it up and fill what is empty.
  useEffect(() => {
    if (!isPincodeReady) return;
    let isCurrent = true;
    lookup(pincode).then(found => {
      if (!isCurrent || !found) return;
      const answer = settle(found);
      setPlace(answer);
      const { form: now, onFieldChange: change } = latest.current;
      if (answer.state && !now[`${prefix}_state`].trim()) change(`${prefix}_state`, answer.state);
      // A district only fits the state it belongs to: fill it when empty and the state is (now) the PIN code's state.
      const stateNow = now[`${prefix}_state`].trim() || answer.state;
      if (answer.district && !now[`${prefix}_district`].trim() && stateNow === answer.state) change(`${prefix}_district`, answer.district);
      if (answer.locality && !now[`${prefix}_village`].trim()) change(`${prefix}_village`, answer.locality);
    });
    return () => { isCurrent = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs when the PIN code changes; `lookup` is stable and `settle` only reads it
  }, [pincode, isPincodeReady, prefix]);

  const known = isPincodeReady && place?.pincode === pincode ? place : null;
  const same = (first: string, second: string) => first.trim().toLowerCase() === second.trim().toLowerCase();
  const isDone = (field: SuggestField) => {
    if (!known) return false;
    if (field === "village") return !!known.locality && same(form[`${prefix}_village`], known.locality);
    const stateFilled = same(form[`${prefix}_state`], known.state);
    return field === "state" ? stateFilled : stateFilled && same(form[`${prefix}_district`], known.district);
  };

  async function suggest(field: SuggestField) {
    if (!isPincodeReady) {
      setNote("Enter the 6-digit PIN code first. Suggest fills the state, district and city from it. You can also choose the state, then the district, then pick the PIN code from the list.");
      return;
    }
    setNote("");
    setSuggesting(field);
    const found = await lookup(pincode);
    setSuggesting(null);
    if (!found) { setNote(`We could not find PIN code ${pincode}. Check it, or choose the state and district yourself.`); return; }
    const answer = settle(found);
    setPlace(answer);
    if (field === "village") {
      if (answer.locality) onFieldChange(`${prefix}_village`, answer.locality);
      else setNote("That PIN code has no area name to suggest. Type the city.");
      return;
    }
    if (answer.state) onFieldChange(`${prefix}_state`, answer.state);
    if (answer.district) onFieldChange(`${prefix}_district`, answer.district);
  }

  return { suggest, suggesting, note, clearNote: () => setNote(""), isPincodeReady, isDone };
}

export default function AddressFields({ form, extras, onFieldChange, onExtrasChange }: Props) {
  const currentSuggest = useAddressSuggest("current", form, onFieldChange);
  const permanentSuggest = useAddressSuggest("permanent", form, onFieldChange);
  const current = usePincodesInDistrict(form.current_state, form.current_district);
  const permanent = usePincodesInDistrict(form.permanent_state, form.permanent_district);

  // Picking a PIN code from the list names its area: use it for the city when the city is still empty.
  function pickPincode(prefix: Prefix, pincode: string, area?: string) {
    onFieldChange(`${prefix}_pin_code`, pincode);
    (prefix === "current" ? currentSuggest : permanentSuggest).clearNote();
    if (area && !form[`${prefix}_village`].trim()) onFieldChange(`${prefix}_village`, area);
  }

  const sameAsCurrent = form.permanent_same_as_current === "true";

  /** City (with Suggest), Landmark and Country of one address: identical for the present and the permanent address. */
  function cityRow(prefix: Prefix) {
    const s = prefix === "current" ? currentSuggest : permanentSuggest;
    const landmarkKey = prefix === "current" ? "landmark" : "permanent_landmark";
    const countryKey = prefix === "current" ? "country" : "permanent_country";
    return (
      <div className="g3" style={{ marginBottom: 14 }}>
        <div className="f">
          <label>City</label>
          <div className="flex gap-2">
            <input value={form[`${prefix}_village`]} onChange={e => onFieldChange(`${prefix}_village`, e.target.value)} className="finput" />
            <SuggestButton onClick={() => s.suggest("village")} isWaiting={!s.isPincodeReady} isDone={s.isDone("village")} isLoading={s.suggesting === "village"} />
          </div>
        </div>
        <div className="f">
          <label>Landmark</label>
          <input value={extras[landmarkKey]} onChange={e => onExtrasChange(landmarkKey, e.target.value)} placeholder="Near…" className="finput" />
        </div>
        <div className="f">
          <label>Country</label>
          <CountrySelect value={extras[countryKey]} onChange={v => onExtrasChange(countryKey, v)} mode="name" inputClassName="finput" />
        </div>
      </div>
    );
  }

  /** State, District and PIN code of one address, in the order they are chosen in, each with its Suggest button. */
  function locationRow(prefix: Prefix) {
    const s = prefix === "current" ? currentSuggest : permanentSuggest;
    const pins = prefix === "current" ? current : permanent;
    const state = form[`${prefix}_state`];
    const district = form[`${prefix}_district`];
    return (
      <>
        <div className="g3" style={{ marginBottom: s.note ? 6 : 10 }}>
          <div className="f">
            <label>State</label>
            <div className="flex gap-2">
              <StateSelect value={state} inputClassName="finput"
                onChange={v => { onFieldChange(`${prefix}_state`, v); onFieldChange(`${prefix}_district`, ""); onFieldChange(`${prefix}_pin_code`, ""); }} />
              <SuggestButton onClick={() => s.suggest("state")} isWaiting={!s.isPincodeReady} isDone={s.isDone("state")} isLoading={s.suggesting === "state"} />
            </div>
          </div>
          <div className="f">
            <label>District</label>
            <div className="flex gap-2">
              <DistrictSelect value={district} state={state} inputClassName="finput"
                onChange={v => { onFieldChange(`${prefix}_district`, v); onFieldChange(`${prefix}_pin_code`, ""); }} />
              <SuggestButton onClick={() => s.suggest("district")} isWaiting={!s.isPincodeReady} isDone={s.isDone("district")} isLoading={s.suggesting === "district"} />
            </div>
          </div>
          <div className="f hw-field" data-hw-invalid={s.note ? "true" : undefined}>
            <label>PIN code</label>
            <PincodeSelect value={form[`${prefix}_pin_code`]} options={pins.options} isLoading={pins.isLoading} inputClassName="finput"
              onChange={(pincode, area) => pickPincode(prefix, pincode, area)} />
            {pins.options.length > 0 && <div className="hint">{pins.options.length} PIN codes in {district}</div>}
          </div>
        </div>
        {s.note && <p className="hint bad" role="status" style={{ margin: "0 0 10px" }}>{s.note}</p>}
      </>
    );
  }

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

      {locationRow("current")}

      {cityRow("current")}

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
          {locationRow("permanent")}
          {cityRow("permanent")}
        </>
      )}
    </div>
  );
}
