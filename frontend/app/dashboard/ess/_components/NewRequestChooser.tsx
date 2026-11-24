"use client";

// "New request" on the My requests tab: pick what kind of request to raise. HR help opens the existing HR help dialog,
// Work from home opens the existing WFH form; this only routes to them.

import { tr } from "@/lib/i18n/tr";
import Modal from "@/components/Modal";

export type NewRequestKind = "hr_help" | "wfh";

interface NewRequestChooserProps {
  onChoose: (kind: NewRequestKind) => void;
  onClose: () => void;
}

const CHOICES: { kind: NewRequestKind; icon: string; title: string; sub: string }[] = [
  { kind: "hr_help", icon: "ti-headset", title: "HR help request", sub: "Employment letter, payroll or benefits query, workplace support" },
  { kind: "wfh", icon: "ti-home-2", title: "Work from home request", sub: "Ask to work remotely for a date range" },
];

export default function NewRequestChooser({ onChoose, onClose }: NewRequestChooserProps) {
  return (
    <Modal title={tr("New request")} onClose={onClose}>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--on-variant)" }}>{tr("What would you like to request?")}</p>
      <div className="ess-list">
        {CHOICES.map(choice => (
          <button key={choice.kind} className="ess-row ess-row-link" type="button" onClick={() => onChoose(choice.kind)}>
            <div>
              <b><i className={`ti ${choice.icon}`} aria-hidden="true" /> {tr(choice.title)}</b>
              <small>{tr(choice.sub)}</small>
            </div>
            <span className="row-go" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
    </Modal>
  );
}
