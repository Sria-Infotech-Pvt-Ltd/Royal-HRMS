"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import type { InvalidPunch } from "@/types/attendance";

interface Props {
  punch:      InvalidPunch;
  onClose:    () => void;
  onDiscarded: () => void;
}

const MAX_REMARKS = 500;

export default function DiscardPunchModal({ punch, onClose, onDiscarded }: Props) {
  const t = useT();
  const { showToast } = useToast();
  const [remarks, setRemarks]       = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await clientApi.post(API.attendance.invalidPunchDiscard(punch.id), { remarks: remarks.trim() });
      showToast(t("Invalid punch discarded."), "success");
      onDiscarded();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? t("Failed to discard invalid punch.");
      setError(message);
      showToast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={
        <>
          <i className="ti ti-trash" style={{ marginRight: 8, color: "var(--error)" }} />
          {t("Discard Invalid Punch")}
        </>
      }
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>{t("Cancel")}</button>
          <button className="btn btn-filled btn-danger" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <><i className="ti ti-loader-2" /> {t("Discarding…")}</> : t("Discard Punch")}
          </button>
        </>
      }
    >
          {error && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
          )}

          <div className="alert alert-warn mb-16">
            <i className="ti ti-alert-triangle" />
            <span>{t("Device: {device} · {time} — this punch will be permanently discarded.", { device: punch.device_id, time: punch.raw_time })}</span>
          </div>

          <div className="field-group">
            <label className="field-label">{t("Remarks (optional)")}</label>
            <textarea
              className="field-input"
              style={{ minHeight: 72 }}
              placeholder={t("e.g. Accidental duplicate punch")}
              value={remarks}
              maxLength={MAX_REMARKS}
              onChange={e => setRemarks(e.target.value)}
            />
            <div style={{ textAlign: "right", fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
              {remarks.length}/{MAX_REMARKS}
            </div>
          </div>
    </Modal>
  );
}
