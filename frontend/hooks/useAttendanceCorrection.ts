"use client";

import { useState, useCallback } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { PunchType, CorrectionReason } from "@/types/attendance";

interface CorrectionPayload {
  date:               string;
  punch_type:         PunchType;
  correct_in_time?:   string;
  correct_out_time?:  string;
  reason:             CorrectionReason;
  notes?:             string;
}

type NormalisedError = { message?: string };

export function useAttendanceCorrection({ onSuccess }: { onSuccess: () => void }) {
  const { showToast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitCorrection = useCallback(
    async (data: CorrectionPayload) => {
      setIsSubmitting(true);
      try {
        const res = await clientApi.post(API.attendance.correction, data);
        const msg = (res.data as { message?: string })?.message ?? "Correction request submitted.";
        showToast(msg, "success");
        onSuccess();
      } catch (err: unknown) {
        const e = err as NormalisedError;
        showToast(e?.message ?? "Failed to submit correction. Please try again.", "error");
      } finally {
        setIsSubmitting(false);
      }
    },
    [onSuccess, showToast]
  );

  return { submitCorrection, isSubmitting };
}
