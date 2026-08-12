"use client";

import { use, useState } from "react";
import Link from "next/link";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { SeparationRequest } from "@/types/separation";
import { useSeparationAccess } from "../_access";
import { statusBadgeClass } from "../_workflow";
import SeparationFormModal from "../_components/SeparationFormModal";
import DecisionModal from "../_components/DecisionModal";
import ConfirmModal from "../_components/ConfirmModal";
import EmployeeDetailsSection from "./_components/EmployeeDetailsSection";
import SeparationDetailsSection from "./_components/SeparationDetailsSection";
import ApprovalSection from "./_components/ApprovalSection";
import KtHandoverSection from "./_components/KtHandoverSection";
import ClearanceSection from "./_components/ClearanceSection";
import DocumentsSection from "./_components/DocumentsSection";
import ActivitySection from "./_components/ActivitySection";

export default function SeparationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const access = useSeparationAccess();
  const { showToast } = useToast();

  const { data: r, loading, error, refetch } = useFetch<SeparationRequest>(API.separation.detail(id));

  const [editing,    setEditing]    = useState(false);
  const [decision,   setDecision]   = useState<{ stageId: string; action: "approve" | "reject" } | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [deleting,   setDeleting]   = useState(false);
  const [working,    setWorking]    = useState(false);

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function handleDecisionConfirm(remarks: string) {
    if (!decision || !r) return;
    setWorking(true);
    try {
      await clientApi.post(API.separation.stageAction(r.id, decision.stageId), { action: decision.action, remarks });
      showToast(decision.action === "approve" ? "Stage approved." : "Stage rejected.", "success");
      setDecision(null);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to submit the decision."), "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleCancelConfirm() {
    if (!r) return;
    setWorking(true);
    try {
      await clientApi.patch(API.separation.detail(r.id), { action: "cancel" });
      showToast("Separation request cancelled.", "success");
      setCancelling(false);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to cancel the request."), "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!r) return;
    setWorking(true);
    try {
      await clientApi.delete(API.separation.detail(r.id));
      showToast("Separation request deleted.", "success");
      window.location.href = "/dashboard/separation";
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to delete the request."), "error");
      setWorking(false);
      setDeleting(false);
    }
  }

  if (loading) {
    return <div style={{ padding: 48, textAlign: "center", color: "var(--on-variant)" }}><i className="ti ti-loader-2 spin" /> Loading…</div>;
  }

  if (error || !r) {
    return (
      <div className="card" style={{ padding: 48, textAlign: "center", maxWidth: 480, margin: "40px auto" }}>
        <i className="ti ti-file-off" style={{ fontSize: 40, color: "var(--outline)", display: "block", marginBottom: 12 }} />
        <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--on-bg)", marginBottom: 6 }}>Request not found</h3>
        <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>
          {error || `No separation request exists with ID ${id}.`}
        </p>
        <Link href="/dashboard/separation" className="btn btn-filled">
          <i className="ti ti-arrow-left" /> Back to Separation & Exit
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <nav style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
            <Link href="/dashboard/separation" style={{ color: "var(--on-variant)" }}>Separation & Exit</Link>
            <i className="ti ti-chevron-right" style={{ fontSize: 10, margin: "0 4px" }} />
            <span style={{ color: "var(--on-bg)", fontWeight: 500 }}>{r.request_ref}</span>
          </nav>
          <div className="page-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {r.employee_name}
            <span className={`badge ${statusBadgeClass(r.status)}`}>{r.status_display}</span>
          </div>
          <div className="page-sub">{r.employee_code} · {r.employee_department} · {r.employee_designation}</div>
        </div>
        <div className="page-actions">
          {r.can_edit && (
            <button className="btn btn-outline" onClick={() => setEditing(true)} suppressHydrationWarning>
              <i className="ti ti-edit" /> Edit
            </button>
          )}
          {r.can_cancel && (
            <button className="btn btn-ghost" onClick={() => setCancelling(true)} suppressHydrationWarning>
              <i className="ti ti-ban" /> Cancel Request
            </button>
          )}
          {r.can_delete && (
            <button className="btn btn-danger" onClick={() => setDeleting(true)} suppressHydrationWarning>
              <i className="ti ti-trash" /> Delete
            </button>
          )}
        </div>
      </div>

      <EmployeeDetailsSection r={r} />
      <SeparationDetailsSection r={r} />
      <ApprovalSection r={r} onDecide={(stageId, action) => setDecision({ stageId, action })} />
      <KtHandoverSection r={r} access={access} />
      <ClearanceSection r={r} />
      <DocumentsSection r={r} access={access} />
      <ActivitySection r={r} />

      {editing && (
        <SeparationFormModal
          mode="edit"
          existing={r}
          canPickEmployee={access.canPickEmployee}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); showToast("Separation request updated.", "success"); refetch(); }}
        />
      )}

      {decision && (
        <DecisionModal
          action={decision.action}
          employeeName={r.employee_name}
          saving={working}
          onClose={() => setDecision(null)}
          onConfirm={handleDecisionConfirm}
        />
      )}

      {cancelling && (
        <ConfirmModal
          title="Cancel Separation Request"
          body={`This will cancel the separation request for ${r.employee_name}. This cannot be undone.`}
          confirmLabel="Yes, Cancel Request"
          danger
          saving={working}
          onConfirm={handleCancelConfirm}
          onCancel={() => setCancelling(false)}
        />
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Separation Request"
          body={`This will permanently delete the separation request for ${r.employee_name}.`}
          confirmLabel="Yes, Delete"
          danger
          saving={working}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleting(false)}
        />
      )}
    </div>
  );
}
