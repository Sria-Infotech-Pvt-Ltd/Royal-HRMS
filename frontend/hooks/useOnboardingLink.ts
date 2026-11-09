"use client";

import { useEffect, useState } from "react";
import clientApi, { resetSessionExpired } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { saveAuth } from "@/lib/auth";
import type { OnboardingLinkResponse } from "@/types/onboardingLink";

export type OnboardingLinkState = "checking" | "opened" | "refused";

/** Exchanges the one-time onboarding link for a limited candidate session (no password, no account yet). */
export function useOnboardingLink(token: string | undefined) {
  const [state, setState] = useState<OnboardingLinkState>("checking");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) return;
    let isCancelled = false;
    clientApi
      .post<OnboardingLinkResponse>(API.auth.onboardingLink, { token })
      .then(response => {
        if (isCancelled) return;
        const user = response.data.data.user;
        saveAuth({
          userId: user.id,
          email: user.email,
          name: user.full_name,
          designation: user.designation ?? "",
          branch: user.branch ?? "",
          permissions: user.permissions ?? [],
          onboarding_status: user.onboarding_status ?? "pending",
          requires_self_service_onboarding: user.requires_self_service_onboarding ?? true,
          assessment_status: user.assessment_status ?? "complete",
          can_manage_team: user.can_manage_team ?? false,
          can_manage_branch: user.can_manage_branch ?? false,
          is_superuser: false,
        });
        resetSessionExpired();
        setState("opened");
      })
      .catch((err: unknown) => {
        if (isCancelled) return;
        const text = (err as { message?: string })?.message;
        setMessage(text || "This onboarding link is invalid, has expired or has already been used. Ask HR to send you a new one.");
        setState("refused");
      });
    return () => { isCancelled = true; };
  }, [token]);

  return { state, message };
}
