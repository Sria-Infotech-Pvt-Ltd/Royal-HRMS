"use client";

import { useCurrentUser } from "@/hooks/useCurrentUser";

/**
 * Returns true when the current user holds the given permission codename,
 * or is a system_admin (who bypasses all permission checks).
 *
 * Returns false during SSR / before the cookie is read (first render).
 */
export function usePermission(codename: string): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.role === "system_admin") return true;
  return user.permissions.includes(codename);
}

/**
 * Returns true when the current user holds ALL of the given codenames.
 */
export function usePermissions(...codenames: string[]): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.role === "system_admin") return true;
  return codenames.every(c => user.permissions.includes(c));
}

/**
 * Returns true when the current user holds ANY of the given codenames.
 */
export function useAnyPermission(...codenames: string[]): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.role === "system_admin") return true;
  return codenames.some(c => user.permissions.includes(c));
}
