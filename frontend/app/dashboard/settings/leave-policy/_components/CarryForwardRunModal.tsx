"use client";

import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";

interface Props {
  fromYear:     number;
  toYear:       number;
  pendingCount: number | null;
  running:      boolean;
  onConfirm:    () => void;
  onClose:      () => void;
}

export default function CarryForwardRunModal({ fromYear, toYear, pendingCount, running, onConfirm, onClose }: Props) {
  const t = useT();
  return (
    <Modal
      title={<><i className="ti ti-alert-triangle" style={{ marginRight: 8 }} />{t("Run Carry Forward")}</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={running}>{t("Cancel")}</button>
          <button className="btn btn-filled" style={{ background: "var(--error-solid)" }} onClick={onConfirm} disabled={running}>
            {running ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />&nbsp;{t("Running…")}</> : t("Run Carry Forward")}
          </button>
        </>
      }
    >
      <p style={{ fontSize: 13, lineHeight: 1.6, color: "var(--on-bg)" }}>
        {t("This will carry forward unused leave")}
        {pendingCount !== null ? " " + (pendingCount === 1 ? t("for {count} employee-leave combination", { count: pendingCount }) : t("for {count} employee-leave combinations", { count: pendingCount })) : ""}{" "}
        {t("from")} <strong>{fromYear}</strong> {t("to")} <strong>{toYear}</strong>. {t("This cannot be undone. Continue?")}
      </p>
    </Modal>
  );
}
