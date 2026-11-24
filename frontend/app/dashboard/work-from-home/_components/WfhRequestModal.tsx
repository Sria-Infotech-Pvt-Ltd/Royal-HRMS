"use client";

// The existing Work From Home request form, opened in a dialog. Used by the My workspace Attendance and Requests tabs so an
// employee can ask for WFH where they already are. Nothing is duplicated: it is the same RequestWfhForm (same validation,
// same saved locations, same POST to /wfh/requests/, same approval flow) as the standalone Work From Home page.

import { useT } from "@/hooks/useI18n";
import Modal from "@/components/Modal";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import RequestWfhForm from "./RequestWfhForm";

interface WfhRequestModalProps {
  onClose: () => void;
  /** Called once the request is saved (before the dialog is closed), so the host can refresh its WFH list. */
  onCreated: (request: WorkFromHomeRequest) => void;
}

export default function WfhRequestModal({ onClose, onCreated }: WfhRequestModalProps) {
  const t = useT();
  // scrollBody pins the header and scrolls only the form, so a long form never pushes its Submit button off-screen on a
  // short window; the width is wide enough for the form's two columns and is still capped at 95vw on a phone.
  return (
    <Modal title={t("Request work from home")} onClose={onClose} size="lg" maxWidth={980} scrollBody>
      <RequestWfhForm variant="modal" onCreated={onCreated} onSubmitted={onClose} />
    </Modal>
  );
}
