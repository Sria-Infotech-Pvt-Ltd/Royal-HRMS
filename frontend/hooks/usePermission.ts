"use client";

import { useCurrentUser } from "@/hooks/useCurrentUser";

export function usePermission(codename: string): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.is_superuser) return true;
  return user.permissions.includes(codename);
}

export function usePermissions(...codenames: string[]): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.is_superuser) return true;
  return codenames.every(c => user.permissions.includes(c));
}

export function useAnyPermission(...codenames: string[]): boolean {
  const user = useCurrentUser();
  if (!user) return false;
  if (user.is_superuser) return true;
  return codenames.some(c => user.permissions.includes(c));
}
