"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function OnboardingApprovalsRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/dashboard/candidate-review?tab=onboarding"); }, [router]);
  return null;
}
