"use client";

// A slim line above the steps: the Company Code as it will be named, so the person always sees what they are building.

import type { BranchForm } from "./_data";

interface Props {
  form: BranchForm;
  /** "City, State" once both are chosen. */
  placeLabel: string;
  codeLoading: boolean;
}

export default function BranchFormSummary({ form, placeLabel, codeLoading }: Props) {
  const hasCode = !!form.branch_code && !codeLoading;
  return (
    <div role="status" aria-label="Company Code summary" style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", marginBottom: 20, borderRadius: 12, background: "var(--bg-low)", border: "1px solid var(--outline-v)" }}>
      <span aria-label="Company Code preview" style={{
        minWidth: 56, textAlign: "center", padding: "5px 10px", borderRadius: 8, fontFamily: "monospace", fontWeight: 800, letterSpacing: ".08em", fontSize: 14,
        background: hasCode ? "var(--primary)" : "var(--surface)", color: hasCode ? "#fff" : "var(--outline)", border: hasCode ? "none" : "1px dashed var(--outline-v)",
      }}>
        {codeLoading ? "…" : form.branch_code || "CODE"}
      </span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: form.branch_name ? "var(--on-bg)" : "var(--outline)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {form.branch_name || "New Company Code"}
        </div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{placeLabel || "Location not chosen yet"}</div>
      </div>
    </div>
  );
}
