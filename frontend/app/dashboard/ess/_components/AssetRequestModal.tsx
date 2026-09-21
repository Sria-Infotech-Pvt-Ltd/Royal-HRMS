"use client";

// "Request an asset" modal — submits via the generic HR Help support-request
// endpoint (see PoliciesAssetsTab.tsx header comment for why: no dedicated
// asset-request model exists, and this reuses the existing one rather than
// adding a new Django app/model for a single free-text request). The asset
// type/needed-by/business-need fields are folded into HRHelpRequest.message
// since that model only stores topic + priority + free text.

import { useState } from "react";
import Modal from "@/components/Modal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// Matches the fields this tab reads off HRHelpRequestSerializer — kept local
// (not the full ApiHrHelpRequest shape from HrHelpTab.tsx) since this tab
// only ever displays a filtered subset of HR Help requests.
export interface ApiHrHelpRequestLite {
  id: string;
  topic: string;
  message: string;
  status: "open" | "in_progress" | "resolved";
  status_display: string;
  created_at: string;
}

export const ASSET_REQUEST_TOPIC = "asset_request";

const ASSET_TYPES = [
  { value: "Laptop", label: "Laptop" },
  { value: "Monitor", label: "Monitor" },
  { value: "Mobile phone", label: "Mobile phone" },
  { value: "Access badge", label: "Access badge" },
  { value: "Other", label: "Other" },
];

interface Props {
  onClose: () => void;
  onSubmitted: () => void;
}

export default function AssetRequestModal({ onClose, onSubmitted }: Props) {
  const [assetType, setAssetType] = useState(ASSET_TYPES[0].value);
  const [neededBy, setNeededBy] = useState("");
  const [businessNeed, setBusinessNeed] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (businessNeed.trim().length < 10) {
      setError("Please describe the business need in at least 10 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const message = `Asset requested: ${assetType}. Needed by: ${neededBy || "Not specified"}. Business need: ${businessNeed.trim()}`;
      await clientApi.post(API.hrHelp.list, { topic: ASSET_REQUEST_TOPIC, priority: "normal", message });
      onSubmitted();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-device-laptop" /> Request an asset</>}
      onClose={onClose}
      closeDisabled={submitting}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit request"}
          </button>
        </>
      }
    >
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
      <div className="field-group" style={{ marginBottom: 16 }}>
        <label className="field-label">Asset type</label>
        <select className="field-input field-select" value={assetType} onChange={e => setAssetType(e.target.value)}>
          {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      <div className="field-group" style={{ marginBottom: 16 }}>
        <label className="field-label">Needed by</label>
        <input
          type="date"
          className="field-input"
          value={neededBy}
          onChange={e => setNeededBy(e.target.value)}
        />
      </div>
      <div className="field-group">
        <label className="field-label">Business need</label>
        <textarea
          className="field-input"
          rows={3}
          value={businessNeed}
          onChange={e => setBusinessNeed(e.target.value)}
          placeholder="Describe why this asset is needed"
        />
      </div>
    </Modal>
  );
}
