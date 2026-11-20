"use client";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { supportTargetFor, type SupportTarget } from "@/lib/supportLink";

/** Where Support / Contact HR should lead for the signed-in person (see lib/supportLink.ts). */
export function useSupportTarget(): SupportTarget {
  return supportTargetFor(useCurrentUser());
}
