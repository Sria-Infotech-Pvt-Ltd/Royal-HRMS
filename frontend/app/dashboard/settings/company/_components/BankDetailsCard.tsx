"use client";

import type { CompanySectionProps } from "@/types/company";
import { BANK_ACCOUNT_TYPE_OPTIONS } from "../_data";

export default function BankDetailsCard({ form, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-building-bank" /> Bank Details</div>
      </div>
      <div className="form-row cols-2" style={{ padding: "20px 24px" }}>
        <div className="field-group">
          <label className="field-label">Account Holder Name</label>
          <input
            className="field-input"
            value={form.bank_account_holder}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_holder", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Account Number</label>
          <input
            className="field-input"
            value={form.bank_account_number}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_number", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">IFSC Code</label>
          <input
            className="field-input"
            value={form.bank_ifsc}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_ifsc", e.target.value.toUpperCase())}
            maxLength={11}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Account Type</label>
          <select
            className="field-input"
            value={form.bank_account_type}
            disabled={!canEdit}
            onChange={e => onFieldChange("bank_account_type", e.target.value)}
          >
            <option value="">Select…</option>
            {BANK_ACCOUNT_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}
