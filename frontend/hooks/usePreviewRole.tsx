"use client";

// "Preview as" — lets an admin/superuser see the Employee Directory as if
// they held a different role's permissions, purely so they can check what
// e.g. a Reporting Manager or Employee would see (masked salary, masked
// PAN/Aadhaar, etc.) without actually logging in as one.
//
// This is COSMETIC ONLY and scoped to the directory/drawer UI — it never
// reaches the backend, and it must never be consulted by anything that
// calls a real mutating endpoint (edit/reveal actions always check the
// user's own real usePermission()/useAnyPermission(), not this). Wiring
// this into the shared usePermission() hook itself was deliberately
// avoided — that hook backs every permission check across the whole app,
// including real edit/delete/approve actions, and a preview override
// leaking into those would be a security bug, not a demo feature.
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { usePermission } from "@/hooks/usePermission";

interface PreviewRoleContextValue {
  previewRoleId: string | null;
  previewRoleName: string | null;
  previewPermissions: string[] | null;
  setPreview: (roleId: string | null, roleName: string | null, permissions: string[]) => void;
}

const PreviewRoleContext = createContext<PreviewRoleContextValue | null>(null);

export function PreviewRoleProvider({ children }: { children: ReactNode }) {
  const [previewRoleId, setPreviewRoleId] = useState<string | null>(null);
  const [previewRoleName, setPreviewRoleName] = useState<string | null>(null);
  const [previewPermissions, setPreviewPermissions] = useState<string[] | null>(null);

  const value = useMemo<PreviewRoleContextValue>(() => ({
    previewRoleId,
    previewRoleName,
    previewPermissions,
    setPreview: (roleId, roleName, permissions) => {
      setPreviewRoleId(roleId);
      setPreviewRoleName(roleName);
      setPreviewPermissions(roleId ? permissions : null);
    },
  }), [previewRoleId, previewRoleName, previewPermissions]);

  return <PreviewRoleContext.Provider value={value}>{children}</PreviewRoleContext.Provider>;
}

export function usePreviewRole() {
  const ctx = useContext(PreviewRoleContext);
  if (!ctx) {
    // Outside a provider, behave as "no preview active" — every consumer
    // falls back to the user's real permissions.
    return { previewRoleId: null, previewRoleName: null, previewPermissions: null, setPreview: () => {} };
  }
  return ctx;
}

/**
 * UI-only permission check for directory/drawer rendering: while a preview
 * role is active, evaluates against that role's permission list instead of
 * the current user's own. Falls back to the real usePermission() the rest
 * of the time. Never use this for a check that gates an actual mutation.
 */
export function useDirectoryPermission(codename: string): boolean {
  const real = usePermission(codename);
  const { previewPermissions } = usePreviewRole();
  if (previewPermissions) return previewPermissions.includes(codename);
  return real;
}
