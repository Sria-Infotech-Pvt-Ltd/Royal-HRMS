"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { Position } from "@/types/orgStructure";

interface Props {
  position: Position | null;
  onClose: () => void;
  onDeactivated: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function DeactivatePositionModal({ position, onClose, onDeactivated }: Props) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!position) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await clientApi.post(API.orgStructure.positions.deactivate(position.id));
      onDeactivated();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to deactivate this position.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!position) return null;

  return (
    <Modal
      title={<><i className="ti ti-eye-off" style={{ marginRight: 8 }} />Deactivate position</>}
      onClose={onClose}
      maxWidth={440}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-danger" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Deactivating…</> : "Deactivate position"}
          </button>
        </>
      }
    >
      {submitError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> <div>{submitError}</div>
        </div>
      )}

      <div style={{ fontSize: 13, marginBottom: 14 }}>
        <b>{position.title}</b> · {position.org_unit_name}
      </div>

      {position.holder_name && (
        <div className="alert alert-warn mb-16" style={{ alignItems: "flex-start" }}>
          <i className="ti ti-alert-triangle" />
          <div>
            This position currently has an active holder, <b>{position.holder_name}</b>. Deactivating
            it does <b>not</b> end their placement or vacate the seat — the position will just show as
            <b> Inactive</b>. Vacate it first if that&apos;s what you actually want.
          </div>
        </div>
      )}

      {position.is_chief && (
        <div className="alert alert-warn mb-16" style={{ alignItems: "flex-start" }}>
          <i className="ti ti-crown" />
          <div>
            This is the <b>chief</b> position for {position.org_unit_name}. Deactivating it leaves the
            unit without a visible head until another position is marked chief.
          </div>
        </div>
      )}

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        Deactivated positions keep their full placement history and stay visible in the tree, tagged
        <b> Inactive</b> — nothing is deleted, and this can be reversed at any time.
      </div>
    </Modal>
  );
}
