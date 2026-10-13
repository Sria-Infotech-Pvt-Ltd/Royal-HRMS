"use client";

// "Proofs" card of the Tax tab: one row per item the employee claimed (rent, 80C items, health
// insurance, loan interest ...) with the proof documents uploaded for it and an Upload action.
// Proofs are stored as document submissions tagged with the item (see EmployeeDocumentSubmission.tax_item).

import { useState } from "react";
import { useMyDocuments, type ApiDocumentSubmission, type DocumentStatus } from "@/hooks/useMyDocuments";
import { useTaxDeclarationSchema } from "@/hooks/useTaxDeclaration";
import { proofItems } from "@/lib/taxDeclarationForm";
import type { ApiTaxDeclaration, TaxProofItem } from "@/types/taxDeclaration";
import TaxProofUploadModal from "./TaxProofUploadModal";

interface Props {
  declaration: ApiTaxDeclaration | null;
}

const STATUS_BADGE: Record<DocumentStatus, string> = { pending: "badge-warn", verified: "badge-success", rejected: "badge-error" };

function formatInr(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

/** The weakest state across an item's proofs: any rejected -> rejected, else any pending -> pending, else verified. */
function overallStatus(proofs: ApiDocumentSubmission[]): DocumentStatus {
  if (proofs.some(proof => proof.status === "rejected")) return "rejected";
  if (proofs.some(proof => proof.status === "pending")) return "pending";
  return "verified";
}

export default function TaxProofsCard({ declaration }: Props) {
  const { data: schema } = useTaxDeclarationSchema();
  const { submissions, loading, error, submit, submitting, submitError } = useMyDocuments();
  const [uploadFor, setUploadFor] = useState<TaxProofItem | null>(null);

  const items = declaration && schema ? proofItems(declaration, schema) : [];
  const isLocked = declaration?.status === "approved";

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-paperclip" /> Investment proofs</div>
      </div>
      <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
        Upload a receipt or certificate for each item you claimed. Payroll verifies them before they count in full.
      </p>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {items.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-paperclip" />
          <h3>{declaration?.tax_regime === "new" ? "No proofs needed under the new regime" : "Nothing to prove yet"}</h3>
          <p>{declaration?.tax_regime === "new" ? "Only the old regime has deductions that need proof." : "Declare your investments first, then upload the proofs here."}</p>
        </div>
      ) : (
        <div style={{ padding: "4px 24px 16px" }}>
          {items.map(item => (
            <ProofRow
              key={item.key}
              item={item}
              proofs={submissions.filter(submission => submission.tax_item === item.key)}
              isLoading={loading}
              isLocked={isLocked}
              onUpload={() => setUploadFor(item)}
            />
          ))}
        </div>
      )}
      {uploadFor && (
        <TaxProofUploadModal
          item={uploadFor} submit={submit} submitting={submitting} submitError={submitError}
          onClose={() => setUploadFor(null)} onUploaded={() => setUploadFor(null)}
        />
      )}
    </div>
  );
}

function ProofRow({ item, proofs, isLoading, isLocked, onUpload }: {
  item: TaxProofItem;
  proofs: ApiDocumentSubmission[];
  isLoading: boolean;
  isLocked: boolean;
  onUpload: () => void;
}) {
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--outline-v)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{item.label}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Claimed {formatInr(item.declared)} · Proof: {item.proof}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          {proofs.length > 0
            ? <span className={`badge ${STATUS_BADGE[overallStatus(proofs)]}`}>{overallStatus(proofs).toUpperCase()}</span>
            : !isLoading && <span className="badge badge-neutral">NOT UPLOADED</span>}
          <button className="btn btn-ghost btn-sm" onClick={onUpload} disabled={isLocked} suppressHydrationWarning>
            <i className="ti ti-upload" /> Upload
          </button>
        </div>
      </div>
      {proofs.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {proofs.map(proof => (
            <span key={proof.id} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, padding: "3px 8px", borderRadius: 6, background: "var(--bg-high)" }}>
              <i className="ti ti-file" />
              {proof.file_url
                ? <a href={proof.file_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--primary)" }}>{proof.file_name}</a>
                : proof.file_name}
              {proof.reference_number && <span style={{ color: "var(--on-variant)" }}>· No. {proof.reference_number}</span>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
