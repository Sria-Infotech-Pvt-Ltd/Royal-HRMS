"use client";

// One employee's onboarding history plus the resend action, so the panel only renders.

import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import type { OnboardingHistory } from "@/types/onboardingHistory";

export function useOnboardingHistory(employeeUuid: string, onChanged: () => void) {
  const { data, loading, error, refetch } = useFetch<OnboardingHistory>(API.employees.onboardingHistory(employeeUuid));
  const { showToast } = useToast();
  const { handleError, formError, clearAll } = useApiErrors();
  const [isResending, setIsResending] = useState(false);

  /** `correctedEmail` is sent only when HR typed a new address to replace a wrong one. */
  async function resend(correctedEmail?: string): Promise<boolean> {
    clearAll();
    setIsResending(true);
    try {
      await clientApi.post(API.employees.resendInvite(employeeUuid), correctedEmail ? { email: correctedEmail } : {});
      showToast("Onboarding email resent.", "success");
      return true;
    } catch (err: unknown) {
      handleError(err, "Could not resend the onboarding email.");
      return false;
    } finally {
      // Failed sends are still written to the history, so show them either way.
      setIsResending(false);
      refetch();
      onChanged();
    }
  }

  return { history: data, loading, error, resend, isResending, resendError: formError };
}
