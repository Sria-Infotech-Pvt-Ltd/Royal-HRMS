"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { FaceIdGuidance } from "@/types/faceId";

/**
 * Face ID for the signed-in person, from one server answer: whether it is required, who registers it (the
 * organisation's mode), this person's state, the one instruction to show, and whether a punch without a face match is
 * currently allowed. Every Face ID screen reads this, so they all say the same thing.
 */
export function useFaceVerificationStatus() {
  const { data, loading, refetch } = useFetch<FaceIdGuidance>(API.attendance.faceVerification.status);
  return {
    isMandatory: data?.is_mandatory ?? false,
    registrationMode: data?.registration_mode ?? "self_service_hr_approval",
    state: data?.state ?? "not_registered",
    canSelfRegister: data?.can_self_register ?? false,
    requiresFaceToPunch: data?.requires_face_to_punch ?? false,
    message: data?.message ?? "",
    fallbackActive: data?.fallback_active ?? false,
    fallbackUntil: data?.fallback_until ?? null,
    hrNote: data?.hr_note ?? "",
    loading,
    refetch,
  };
}
