"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { directoryStatusLabel, fullName, initials, personAvatarTint, type DirectoryStatusLabel, type Employee } from "../_data";
import type { StatusPillTone } from "@/components/employees/StatusPill";
import Avatar from "./Avatar";
import EmployeeRowActionsMenu, { type RowAction } from "./EmployeeRowActionsMenu";
import PerformActionModal from "./PerformActionModal";
import StatusPill from "@/components/employees/StatusPill";
import { formatDateSlash } from "@/lib/formatDate";
import { usePermission } from "@/hooks/usePermission";
import type { ActionType } from "./PerformActionFields/types";

// The Employee Directory reference shows dd/mm/yyyy, so the table (like its drawer) uses the slash style.
function slashDate(iso: string | null | undefined): string {
  return formatDateSlash(iso) || "—";
}

const STATUS_TONE: Record<DirectoryStatusLabel, StatusPillTone> = {
  Active: "success", Onboarding: "warn", Probation: "brand", "Notice Period": "error", Exited: "neutral",
};

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
  const rowStatus = directoryStatusLabel(e);
  const isExited = e.status === "inactive";
  const tint = personAvatarTint(e.id);
  const [showActionModal, setShowActionModal] = useState(false);
  // A Reporting Manager has no employees.edit but may raise an action for approval.
  const canRaiseAction = usePermission("employees.raise_action");
  const canConfirm = usePermission("employees.confirm");
  const [initialActionType, setInitialActionType] = useState<ActionType | undefined>();

  const actions: RowAction[] = [
    { label: "View", icon: "ti-eye", onClick: () => onOpen(e.id) },
    ...(canConfirm && e.status === "active" && e.employmentStatus === "probation"
      ? [{
          label: "Confirm probation",
          icon: "ti-user-check",
          tone: "success" as const,
          onClick: () => {
            setInitialActionType("confirmation");
            setShowActionModal(true);
          },
        }]
      : []),
    ...(canEditOnboarding && e.status === "onboarding"
      ? [{ label: "Complete onboarding", icon: "ti-clipboard-check", tone: "warn", onClick: () => router.push(`/dashboard/employees/${e.id}/onboarding`) } satisfies RowAction]
      : []),
    // Replaces the old standalone "Deactivate" toggle — Separation (inside
    // the unified modal below) is the real offboarding path; a manually
    // reactivated/deactivated account outside that flow is still available
    // for admins directly on the Employee Detail page if ever needed.
    ...((canEdit || canRaiseAction) && !isExited
      ? [{
          label: "Perform an action",
          icon: "ti-bolt",
          onClick: () => {
            setInitialActionType(undefined);
            setShowActionModal(true);
          },
        } satisfies RowAction]
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
        <StatusPill label={rowStatus} tone={STATUS_TONE[rowStatus]} />
      </div>
      <div className="text-[13px] whitespace-nowrap" style={{ color: "var(--muted)" }}>{slashDate(e.dateOfJoining)}</div>
      <div className="text-[13px] whitespace-nowrap">
        {rowStatus === "Notice Period" || isExited
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
            initialActionType={initialActionType}
            onClose={() => {
              setShowActionModal(false);
              setInitialActionType(undefined);
            }}
            onApplied={onActionApplied}
          />
        )}
      </div>
    </div>
  );
}
