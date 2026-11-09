"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { HrContact } from "@/types/onboardingLink";

/** The HR user dealing with the signed-in candidate, or null when none is assigned (or it can't be loaded). */
export function useHrContact(isEnabled: boolean): HrContact | null {
  const [contact, setContact] = useState<HrContact | null>(null);

  useEffect(() => {
    if (!isEnabled) return;
    let isCancelled = false;
    clientApi
      .get<{ data: HrContact }>(API.auth.onboardingHrContact)
      .then(response => {
        const data = response.data.data;
        if (!isCancelled && data.email) setContact(data);
      })
      .catch(() => { /* the contact line is a convenience; the page works without it */ });
    return () => { isCancelled = true; };
  }, [isEnabled]);

  return contact;
}
