"use client";

// "View workspace": opens an employee's own workspace (the screen they see after login), read-only. Shown only to
// people the server allows to (employees.view_workspace); everyone else sees nothing.

import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { viewWorkspacePath } from "@/lib/viewAs";

interface Props {
  employeeUuid: string | undefined;
  className?: string;
  style?: React.CSSProperties;
}

export default function ViewWorkspaceButton({ employeeUuid, className, style }: Props) {
  const router = useRouter();
  const canView = usePermission("employees.view_workspace");
  if (!canView || !employeeUuid) return null;

  return (
    <button type="button" className={className} style={style} onClick={() => router.push(viewWorkspacePath(employeeUuid))} suppressHydrationWarning>
      <i className="ti ti-eye text-[14px]" /> View workspace
    </button>
  );
}
