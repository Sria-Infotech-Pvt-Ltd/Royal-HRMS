"use client";

// Leave data lives in several independently fetched places (balance tiles, "My leave requests", the Home tiles). After anything
// that changes it (submit, cancel, an approval) the screen that did it calls notifyLeaveChanged(); every place showing leave
// data subscribes with useOnLeaveChanged(refetch) and reloads, so nothing stays stale until a manual page refresh.

import { useEffect } from "react";

const LEAVE_CHANGED_EVENT = "hrms:leave-changed";

export function notifyLeaveChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(LEAVE_CHANGED_EVENT));
}

export function useOnLeaveChanged(handler: () => void): void {
  useEffect(() => {
    window.addEventListener(LEAVE_CHANGED_EVENT, handler);
    return () => window.removeEventListener(LEAVE_CHANGED_EVENT, handler);
  }, [handler]);
}
