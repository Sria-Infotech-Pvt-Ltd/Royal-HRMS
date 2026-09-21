"use client";

// "Scan & fill" — uploads a document to the real scan-document endpoint
// (apps.accounts.views_hire_scan), which extracts actual text from a
// text-based PDF and regex-matches known field formats (PAN, Aadhaar,
// email, phone, labeled name/DOB/PIN code) — never a guessed/fabricated
// value. Every suggestion shown here is a literal match found in the
// uploaded document; the user reviews and picks which ones to apply.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";

export interface ScanSuggestions {
  full_name?: string;
  email?: string;
  phone?: string;
  pan_number?: string;
  aadhaar_number?: string;
  date_of_birth?: string;
  current_pin_code?: string;
}

const FIELD_LABELS: Record<keyof ScanSuggestions, string> = {
  full_name: "Full name",
  email: "Email",
  phone: "Mobile number",
  pan_number: "PAN",
  aadhaar_number: "Aadhaar",
  date_of_birth: "Date of birth",
  current_pin_code: "Pincode",
};

interface Props {
  hireActionId: string;
  onClose: () => void;
  onApply: (suggestions: ScanSuggestions) => void;
}

export default function ScanFillModal({ hireActionId, onClose, onApply }: Props) {
  const [scanning, setScanning] = useState(false);
  const [suggestions, setSuggestions] = useState<ScanSuggestions | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setScanning(true);
    setError(null);
    setSuggestions(null);
    setWarnings([]);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await clientApi.post<{ data: { suggestions: ScanSuggestions; warnings: string[] } }>(
        API.hireActions.scanDocument(hireActionId), formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      const found = data.data.suggestions ?? {};
      setSuggestions(found);
      setWarnings(data.data.warnings ?? []);
      setSelected(new Set(Object.keys(found)));
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Could not scan this document. Please try again.");
    } finally {
      setScanning(false);
    }
  }

  function toggle(key: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function apply() {
    if (!suggestions) return;
    const picked: ScanSuggestions = {};
    for (const key of Object.keys(suggestions) as (keyof ScanSuggestions)[]) {
      if (selected.has(key)) picked[key] = suggestions[key];
    }
    onApply(picked);
    onClose();
  }

  const suggestionEntries = suggestions
    ? (Object.entries(suggestions) as [keyof ScanSuggestions, string][])
    : [];

  return (
    <Modal
      title={<><i className="ti ti-scan" style={{ color: "var(--primary)" }} /> Scan &amp; fill</>}
      onClose={onClose}
      zIndex={1100}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={apply} disabled={!suggestions || selected.size === 0}>
            Apply selected
          </button>
        </>
      }
    >
      <p className="hint" style={{ marginBottom: 12 }}>
        Upload a text-based PDF (an offer letter, ID or resume exported as PDF). This reads the
        actual text in the document and matches recognizable fields — it does not guess anything
        not on the page.
      </p>

      <label className="filebtn" style={{ width: "100%", justifyContent: "center", padding: "18px 16px" }}>
        <i className="ti ti-upload" />
        {scanning ? "Scanning…" : "Choose a PDF, JPG or PNG"}
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          disabled={scanning}
          onChange={e => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) handleFile(file);
          }}
        />
      </label>

      {error && (
        <div className="note warn" style={{ marginTop: 12 }}>{error}</div>
      )}

      {warnings.map((w, i) => (
        <div key={i} className="note warn" style={{ marginTop: 12 }}>{w}</div>
      ))}

      {suggestionEntries.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div className="sechead">FOUND IN DOCUMENT</div>
          {suggestionEntries.map(([key, value]) => (
            <label key={key} className="chkline" style={{ padding: "8px 0" }}>
              <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} />
              <span style={{ minWidth: 110 }}>{FIELD_LABELS[key]}</span>
              <span style={{ fontWeight: 400, color: "var(--muted)" }}>{value}</span>
            </label>
          ))}
        </div>
      )}
    </Modal>
  );
}
