"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

export type FaceRegistrationCardState =
  | "disabled"        // org toggle is off — feature switched off, contact admin
  | "not_registered"  // toggle on, no Face ID and no request
  | "pending"         // toggle on, submitted and awaiting HR approval
  | "rejected"        // toggle on, the last submission was rejected
  | "approved";       // toggle on, employee is registered and verified at punch

/**
 * Drives the "Face Registration" card on the employee Profile page. The state, the instruction text and whether the
 * employee may register at all all come from the server's Face ID answer (the organisation's registration mode), so
 * this card says exactly what the clock-in error and the onboarding screens say.
 */
export function useFaceRegistrationCard() {
  const status = useFaceVerificationStatus();
  const { data: registration, loading: registrationLoading, refetch: refetchRegistration } =
    useFetch<Partial<FaceRegistrationRequest>>(API.attendance.faceRegistration.me);

  const state: FaceRegistrationCardState = status.isMandatory ? status.state : "disabled";

  return {
    isMandatory: status.isMandatory,
    state,
    message: status.message,
    canSelfRegister: status.canSelfRegister,
    fallbackActive: status.fallbackActive,
    notes: registration?.notes ?? "",
    loading: status.loading || registrationLoading,
    refetch: () => { status.refetch(); refetchRegistration(); },
  };
}
