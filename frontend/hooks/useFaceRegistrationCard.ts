"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

export type FaceRegistrationCardState =
  | "disabled"        // org toggle is off — feature switched off, contact admin
  | "not_registered"  // toggle on, employee has never submitted a request
  | "pending"         // toggle on, submitted and awaiting HR approval
  | "rejected"        // toggle on, HR rejected the last submission
  | "approved";       // toggle on, employee is registered and verified at punch

/**
 * Drives the "Face Registration" card on the employee Profile page.
 * Combines the org-wide mandatory toggle with the employee's own latest
 * FaceRegistrationRequest so the card can render the right state instead of
 * always showing a "Register My Face" button regardless of admin config.
 */
export function useFaceRegistrationCard() {
  const { isMandatory, loading: statusLoading } = useFaceVerificationStatus();
  const { data: registration, loading: registrationLoading, refetch } =
    useFetch<Partial<FaceRegistrationRequest>>(API.attendance.faceRegistration.me);

  let state: FaceRegistrationCardState = "not_registered";
  if (!isMandatory) {
    state = "disabled";
  } else if (registration?.status === "approved") {
    state = "approved";
  } else if (registration?.status === "pending") {
    state = "pending";
  } else if (registration?.status === "rejected") {
    state = "rejected";
  }

  return {
    isMandatory,
    state,
    notes: registration?.notes ?? "",
    loading: statusLoading || registrationLoading,
    refetch,
  };
}
