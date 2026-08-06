"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface FaceVerificationStatusResponse {
  is_mandatory: boolean;
}

/**
 * Org-wide face ID verification toggle, configured on the Attendance
 * Settings page (Face ID Verification card) and readable by any
 * authenticated employee — not just HR/admin.
 *
 * When mandatory: every employee must register a face ID and every web
 * clock-in/out requires a live face match. When not mandatory: the whole
 * feature is switched off — nobody can register or is asked to verify.
 */
export function useFaceVerificationStatus() {
  const { data, loading } = useFetch<FaceVerificationStatusResponse>(API.attendance.faceVerification.status);
  return {
    isMandatory: data?.is_mandatory ?? false,
    loading,
  };
}
