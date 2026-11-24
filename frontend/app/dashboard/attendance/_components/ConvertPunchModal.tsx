"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import type { InvalidPunch } from "@/types/attendance";

interface Props {
  punch:       InvalidPunch;
  onClose:     () => void;
  onConverted: () => void;
}

export default function ConvertPunchModal({ punch, onClose, onConverted }: Props) {
  const t = useT();
  const { showToast } = useToast();
  const [punchType, setPunchType]   = useState<"IN" | "OUT">("OUT");
  const [targetTime, setTargetTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  async function handleSubmit() {
    if (!targetTime) { setError(t("Please select the target time.")); return; }
    setSubmitting(true);
    setError(null);
    try {
      await clientApi.post(API.attendance.invalidPunchConvert(punch.id), {
        target_punch_type: punchType,
        target_time:       targetTime,
      });
      showToast(t("Invalid punch converted. Attendance record recalculated."), "success");
      onConverted();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? t("Failed to convert invalid punch.");
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
          <i className="ti ti-replace" style={{ marginRight: 8, color: "var(--primary)" }} />
          {t("Convert to Valid Punch")}
        </>
      }
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>{t("Cancel")}</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <><i className="ti ti-loader-2" /> {t("Converting…")}</> : t("Convert to Valid Punch")}
          </button>
        </>
      }
    >
          {error && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
          )}

          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 12 }}>
            {t("Device: {device} · {time}", { device: punch.device_id, time: punch.raw_time })}
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">{t("Punch Type")}</label>
              <select className="field-input field-select" value={punchType} onChange={e => setPunchType(e.target.value as "IN" | "OUT")}>
                <option value="IN">IN</option>
                <option value="OUT">OUT</option>
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">{t("Target Time")}</label>
              <input
                type="time"
                className="field-input"
                value={targetTime}
                onChange={e => setTargetTime(e.target.value)}
              />
            </div>
          </div>
    </Modal>
  );
}
