"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fullName, initials, personAvatarTint, type Employee } from "../_data";
import Avatar from "./Avatar";
import EmployeeRowActionsMenu, { type RowAction } from "./EmployeeRowActionsMenu";
import PerformActionModal from "./PerformActionModal";
import StatusPill from "@/components/employees/StatusPill";

function slashDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

interface Props {
  employee: Employee;
  canEditOnboarding: boolean;
  canEdit: boolean;
  toggling: boolean;
  onOpen: (id: string) => void;
  onToggleStatus: (employee: Employee) => void;
  /** Refetches the directory after a "Perform an action" apply. */
  onActionApplied: () => void;
}

export default function EmployeeTableRow({ employee: e, canEditOnboarding, canEdit, toggling, onOpen, onToggleStatus, onActionApplied }: Props) {
  const router = useRouter();
  const onNotice = e.status === "active" && !!e.lastWorkingDay;
  const isExited = e.status === "inactive";
  const tint = personAvatarTint(e.id);
  const [showActionModal, setShowActionModal] = useState(false);

  const actions: RowAction[] = [
    { label: "View", icon: "ti-eye", onClick: () => onOpen(e.id) },
    ...(canEditOnboarding && e.status === "onboarding"
      ? [{ label: "Complete onboarding", icon: "ti-clipboard-check", tone: "warn", onClick: () => router.push(`/dashboard/employees/${e.id}/onboarding`) } satisfies RowAction]
      : []),
    // Replaces the old standalone "Deactivate" toggle — Separation (inside
    // the unified modal below) is the real offboarding path; a manually
    // reactivated/deactivated account outside that flow is still available
    // for admins directly on the Employee Detail page if ever needed.
    ...(canEdit && !isExited
      ? [{ label: "Perform an action", icon: "ti-bolt", onClick: () => setShowActionModal(true) } satisfies RowAction]
      : []),
    ...(canEdit && isExited
      ? [{ label: "Activate", icon: "ti-user-check", tone: "success", onClick: () => onToggleStatus(e) } satisfies RowAction]
      : []),
  ];

  return (
    <div className="tr grid-cols-emp" onClick={() => onOpen(e.id)}>
      <div className="who">
        <div style={isExited ? { filter: "grayscale(1)", opacity: 0.65 } : undefined}>
          <Avatar text={initials(e.firstName, e.lastName)} size={32} color={tint.bg} textColor={tint.text} shape="square" className="av" photoUrl={e.photoUrl} />
        </div>
        <div className="min-w-0">
          <div className="n truncate">{fullName(e)}</div>
          <div className="i truncate">{e.code}</div>
        </div>
      </div>
      <div className="text-[13px] whitespace-nowrap" style={{ color: "var(--ink)" }}>{e.designation || "—"}</div>
      <div className="dept whitespace-nowrap">
        <div className="text-[13.5px] font-semibold" style={{ color: "var(--ink)" }}>{e.orgUnitName || e.department || "—"}</div>
        {e.orgUnitParentName && <div className="u">{e.orgUnitParentName}</div>}
      </div>
      <div className="text-[13px] whitespace-nowrap" style={{ color: "var(--ink)" }}>
        {e.location || <span style={{ color: "var(--faint)" }}>—</span>}
      </div>
      <div>
        {onNotice
          ? <StatusPill label="Notice Period" tone="error" />
          : e.status === "active"
            ? <StatusPill label="Active" tone="success" />
            : e.status === "onboarding"
              ? <StatusPill label="Onboarding" tone="warn" />
              : <StatusPill label="Exited" tone="neutral" />
        }
      </div>
      <div className="text-[13px] whitespace-nowrap" style={{ color: "var(--muted)" }}>{slashDate(e.dateOfJoining)}</div>
      <div className="text-[13px] whitespace-nowrap">
        {onNotice || isExited
          ? <span className="mgr" style={{ color: "var(--crit)", fontStyle: "italic" }}>Last day {slashDate(e.lastWorkingDay)}</span>
          : e.reportingManagerName
            ? <span className="mgr" style={{ color: "var(--ink)" }}>{e.reportingManagerName}</span>
            : <span className="mgr none">CEO Office</span>
        }
      </div>
      <div onClick={ev => ev.stopPropagation()}>
        <EmployeeRowActionsMenu actions={actions.map(a => ({ ...a, onClick: toggling ? () => {} : a.onClick }))} />
        {showActionModal && (
          <PerformActionModal
            employee={e}
            onClose={() => setShowActionModal(false)}
            onApplied={onActionApplied}
          />
        )}
      </div>
    </div>
  );
}
