"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { getStoredUser } from "@/lib/auth";
import type { UserInfo } from "@/lib/auth";

// getStoredUser() reads document.cookie, which is empty during SSR — reading it
// at render time causes a server/client hydration mismatch. Resolving it in an
// effect keeps first render null on both sides, matching the pattern already
// used across the app (see employees/page.tsx, announcements/page.tsx).
//
// Re-checked on every pathname change, not just on mount. Consumers of this
// hook (e.g. VoiceCommandButton) commonly live in the root layout and are
// never unmounted across a client-side navigation — a mount-only effect
// would freeze `user` at whatever the cookie held on the very first page
// load in the tab (typically null, before login) and never notice a
// login/logout that happens later via router.push() (e.g. app/login/page.tsx's
// saveAuth() + router.push("/dashboard"), which is a soft navigation, not a
// reload). usePathname() is what VoiceCommandButton already tracks for its
// own hide-on-/login logic, so this reuses the same signal rather than
// polling on every render.
//
// The serialized-content check below skips the state update (and the
// re-render it would cause) when the cookie hasn't actually changed since
// the last check — e.g. navigating between two dashboard pages while still
// logged in. Without it, every navigation would call setUser() with a new
// (but equal) object, which doesn't change what isAuthenticated evaluates
// to but would still re-render every consumer for no reason.
export function useCurrentUser(): UserInfo | null {
  const pathname = usePathname();
  const [user, setUser] = useState<UserInfo | null>(null);
  const lastSerializedRef = useRef<string | null>(null);

  useEffect(() => {
    const current = getStoredUser();
    const serialized = current ? JSON.stringify(current) : null;
    if (serialized === lastSerializedRef.current) return;
    lastSerializedRef.current = serialized;
    setUser(current);
  }, [pathname]);

  return user;
}
