"use client";

import { useRouter } from "next/navigation";
import { fullName, initials, personAvatarTint, type Employee } from "../_data";
import Avatar from "./Avatar";
import EmployeeRowActionsMenu, { type RowAction } from "./EmployeeRowActionsMenu";
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
}

export default function EmployeeTableRow({ employee: e, canEditOnboarding, canEdit, toggling, onOpen, onToggleStatus }: Props) {
  const router = useRouter();
  const onNotice = e.status === "active" && !!e.lastWorkingDay;
  const isExited = e.status === "inactive";
  const tint = personAvatarTint(e.id);

  const actions: RowAction[] = [
    { label: "View", icon: "ti-eye", onClick: () => onOpen(e.id) },
    ...(canEditOnboarding && e.status === "onboarding"
      ? [{ label: "Complete onboarding", icon: "ti-clipboard-check", tone: "warn", onClick: () => router.push(`/dashboard/employees/${e.id}/onboarding`) } satisfies RowAction]
      : []),
    ...(canEdit
      ? [{
          label: e.status === "inactive" ? "Activate" : "Deactivate",
          icon: e.status === "inactive" ? "ti-user-check" : "ti-user-off",
          tone: e.status === "inactive" ? "success" : "danger",
          onClick: () => onToggleStatus(e),
        } satisfies RowAction]
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
      </div>
    </div>
  );
}
