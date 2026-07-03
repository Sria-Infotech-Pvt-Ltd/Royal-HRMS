"use client";

import { useEffect, useState } from "react";
import { getStoredUser } from "@/lib/auth";
import type { UserInfo } from "@/lib/auth";

// getStoredUser() reads document.cookie, which is empty during SSR — reading it
// at render time causes a server/client hydration mismatch. Resolving it in an
// effect keeps first render null on both sides, matching the pattern already
// used across the app (see employees/page.tsx, announcements/page.tsx).
export function useCurrentUser(): UserInfo | null {
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  return user;
}
