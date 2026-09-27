"use client";

// The five per-action-type "fields this <action> may change" bodies for
// PerformActionModal — split out purely to keep the orchestrator under the
// file-length guideline; each one is a plain controlled form fragment with
// no fetching or submit logic of its own.

import type { FieldOption } from "../../_data";
import type { ReasonOption } from "./types";
import SearchableSelect from "@/components/SearchableSelect";

interface SelectFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: FieldOption[];
  placeholder: string;
  disabled?: boolean;
}

function SelectField({ label, value, onChange, options, placeholder, disabled }: SelectFieldProps) {
  return (
    <div className="f">
      <label>{label} <span className="req">*</span></label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="finput"
        style={{ cursor: disabled ? "not-allowed" : "pointer" }}
      >
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function ReasonSelect({ reason, setReason, options, actionChosen }: {
  reason: string; setReason: (v: string) => void; options: ReasonOption[]; actionChosen: boolean;
}) {
  return (
    <SelectField
      label="Reason"
      value={reason}
      onChange={setReason}
      options={options}
      placeholder={actionChosen ? "Select a reason" : "Select an action first"}
      disabled={!actionChosen}
    />
  );
}

export function PromotionFields({ positionId, setPositionId, positionOptions, annualCtc, setAnnualCtc }: {
  positionId: string; setPositionId: (v: string) => void; positionOptions: FieldOption[];
  annualCtc: string; setAnnualCtc: (v: string) => void;
}) {
  return (
    <div className="g2">
      <SelectField label="Position" value={positionId} onChange={setPositionId} options={positionOptions} placeholder="Select a position" />
      <div className="f">
        <label>Annual CTC (₹) <span className="text-muted" style={{ fontWeight: 400 }}>(optional)</span></label>
        <input type="number" min={0} step={1000} value={annualCtc} onChange={e => setAnnualCtc(e.target.value)} className="finput" placeholder="e.g. 900000" />
      </div>
    </div>
  );
}

export function OrgAssignmentFields({ managerId, setManagerId, managerOptions, workLocation, setWorkLocation }: {
  managerId: string; setManagerId: (v: string) => void; managerOptions: FieldOption[];
  workLocation: string; setWorkLocation: (v: string) => void;
}) {
  return (
    <div className="g2">
      <div className="f">
        <label>Reporting manager <span className="text-muted" style={{ fontWeight: 400 }}>(optional)</span></label>
        <SearchableSelect value={managerId} onChange={setManagerId} inputClassName="finput" placeholder="Keep current" options={managerOptions} />
      </div>
      <div className="f">
        <label>Work location <span className="text-muted" style={{ fontWeight: 400 }}>(optional)</span></label>
        <input type="text" value={workLocation} onChange={e => setWorkLocation(e.target.value)} className="finput" placeholder="e.g. Hyderabad HQ" />
      </div>
    </div>
  );
}

export function PayChangeFields({ annualCtc, setAnnualCtc }: { annualCtc: string; setAnnualCtc: (v: string) => void }) {
  return (
    <div className="g2">
      <div className="f">
        <label>Annual CTC (₹) <span className="req">*</span></label>
        <input type="number" min={0} step={1000} value={annualCtc} onChange={e => setAnnualCtc(e.target.value)} className="finput" placeholder="e.g. 900000" />
      </div>
    </div>
  );
}

export function ConfirmationFields({ currentStatusLabel }: { currentStatusLabel: string }) {
  return (
    <div className="g2">
      <div className="f">
        <label>Employee status</label>
        <div className="finput" style={{ cursor: "not-allowed" }}>{currentStatusLabel} → Confirmed</div>
      </div>
    </div>
  );
}

export function SeparationFields({
  separationType, setSeparationType, typeOptions,
  lastWorkingDay, setLastWorkingDay, resultingStatusLabel,
}: {
  separationType: string; setSeparationType: (v: string) => void; typeOptions: FieldOption[];
  lastWorkingDay: string; setLastWorkingDay: (v: string) => void; resultingStatusLabel: string;
}) {
  return (
    <div className="g3">
      <SelectField label="Separation type" value={separationType} onChange={setSeparationType} options={typeOptions} placeholder="Select a type" />
      <div className="f">
        <label>Last working day <span className="req">*</span></label>
        <input type="date" value={lastWorkingDay} onChange={e => setLastWorkingDay(e.target.value)} className="finput" />
      </div>
      <div className="f">
        <label>Employee status</label>
        <div className="finput" style={{ cursor: "not-allowed" }}>{resultingStatusLabel}</div>
      </div>
    </div>
  );
}
