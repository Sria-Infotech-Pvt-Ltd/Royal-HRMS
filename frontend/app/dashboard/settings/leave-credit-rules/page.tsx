"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LeaveCreditRulesRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/dashboard/settings/leave-policy"); }, [router]);
  return null;
}
