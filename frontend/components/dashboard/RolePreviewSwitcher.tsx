"use client";

// Global "acting role" switcher in the top nav — lets an admin/HR user
// preview the app as if they held a different role's permissions, purely
// for checking what that role would see (masked salary, masked PAN/
// Aadhaar in the Employee Directory, etc.). This is COSMETIC ONLY: it
// drives usePreviewRole()'s context, which only useDirectoryPermission()
// consults (Employee Directory table/drawer masking) — it is never wired
// into the shared usePermission()/useAnyPermission() hooks that gate real
// edits/approvals/reveals, so a preview can never grant real access it
// doesn't already have. See hooks/usePreviewRole.tsx for the full
// reasoning.
//
// The dropdown list is deliberately fixed to the 4 roles the reference
// mockup shows (HR Business Partner / Payroll Admin / Reporting Manager /
// Employee (self-service)) — not "every Role row in the database" — per
// explicit instruction. This app's real roles don't share those exact
// names, so each mockup label is mapped to the closest real role and its
// real permission set:
//   HR Business Partner  -> hr_admin
//   Payroll Admin        -> branch_admin (the only other real role that,
//                            like hr_admin, already holds payroll.view +
//                            employees.view_sensitive)
//   Reporting Manager    -> manager
//   Employee (self-service) -> employee
// system_admin is intentionally excluded, matching the mockup's own list.

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { usePreviewRole } from "@/hooks/usePreviewRole";
import { useToast } from "@/components/ToastProvider";

const ESS_PATH = "/dashboard/ess";

interface ApiRole {
  id: number;
  name: string;
  display_name: string;
  permissions: string[];
}

interface PreviewOption {
  label: string;
  role: ApiRole;
}

// Exact 4 options, exact order, exact labels — confirmed from the reference
// app's own role-switcher <select>.
const LABEL_BY_ROLE_NAME: Record<string, string> = {
  hr_admin:     "HR Business Partner",
  branch_admin: "Payroll Admin",
  manager:      "Reporting Manager",
  employee:     "Employee (self-service)",
};
const DISPLAY_ORDER = ["hr_admin", "branch_admin", "manager", "employee"];

function previewToastMessage(option: PreviewOption): string {
  const hasPayroll = option.role.permissions.includes("payroll.view");
  const hasSensitive = option.role.permissions.includes("employees.view_sensitive");
  if (hasPayroll || hasSensitive) {
    return `Acting as ${option.label} — Compensation and sensitive fields are visible for this role.`;
  }
  return `Acting as ${option.label} — Compensation and sensitive fields are hidden for this role.`;
}

interface Props {
  currentRoleName: string;
}

export default function RolePreviewSwitcher({ currentRoleName }: Props) {
  // Only shown to someone who could plausibly want to preview a lesser
  // role — the same permission the Employees page itself already gates
  // its own admin-only affordances on.
  const canPreview = usePermission("employees.edit");
  const { showToast } = useToast();
  const { previewRoleId, setPreview } = usePreviewRole();
  const router = useRouter();
  const pathname = usePathname();

  const [options, setOptions] = useState<PreviewOption[]>([]);

  useEffect(() => {
    if (!canPreview) return;
    clientApi
      .get<{ data: { results: ApiRole[] } }>(API.roles.list, { params: { page_size: 100 } })
      .then(r => {
        const roles = r.data.data?.results ?? [];
        const built = DISPLAY_ORDER
          .map(name => {
            const role = roles.find(rl => rl.name === name);
            return role ? { label: LABEL_BY_ROLE_NAME[name], role } : null;
          })
          .filter((o): o is PreviewOption => o !== null);
        setOptions(built);
      })
      .catch(() => {});
  }, [canPreview]);

  if (!canPreview) return null;

  const activeOption = options.find(o => String(o.role.id) === previewRoleId);
  // Native <select> value: the previewed role's name if previewing, else the
  // user's own real role name (only meaningful when it's one of the 4 listed
  // roles — system_admin, intentionally excluded from this list, simply
  // shows the browser's default first-option selection until a preview is
  // picked, matching this component's pre-existing system_admin carve-out).
  const value = activeOption?.role.name ?? currentRoleName;

  function handleChange(roleName: string) {
    // Selecting your own real role — whether to explicitly return to it, or
    // because there was nothing else to pick — clears any active preview.
    if (roleName === currentRoleName) {
      if (activeOption) {
        setPreview(null, null, []);
        showToast("Preview cleared — showing your real access.", "info");
        if (pathname?.startsWith(ESS_PATH)) router.push("/dashboard");
      }
      return;
    }
    const option = options.find(o => o.role.name === roleName);
    if (!option) return;
    setPreview(String(option.role.id), option.label, option.role.permissions);
    showToast(previewToastMessage(option), "info");
    // "Employee (self-service)" is the only preview role with its own
    // dedicated view (the ESS module) — jump straight there so the
    // preview is actually visible, instead of leaving the admin/HR user
    // stranded on their own real dashboard with nothing changed on screen.
    if (option.role.name === "employee") router.push(ESS_PATH);
  }

  return (
    <select
      className="sel"
      value={value}
      onChange={e => handleChange(e.target.value)}
      title="Preview the app as if you held a different role's permissions — your own real access is unchanged."
      suppressHydrationWarning
    >
      {options.map(option => (
        <option key={option.role.id} value={option.role.name}>{option.label}</option>
      ))}
    </select>
  );
}
