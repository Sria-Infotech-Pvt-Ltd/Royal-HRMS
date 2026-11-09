"use client";

// Candidate entry point: the one-time link HR emails after selecting the candidate. It opens a limited
// session (no password, no employee account yet) and sends the candidate to the onboarding wizard.
import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useOnboardingLink } from "@/hooks/useOnboardingLink";

export default function OnboardingStartPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const { state, message } = useOnboardingLink(params.token);

  useEffect(() => {
    if (state === "opened") router.replace("/onboarding");
  }, [state, router]);

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 16, background: "var(--bg, #f6f7f9)" }}>
      <div style={{ maxWidth: 440, textAlign: "center" }}>
        {state === "refused" ? (
          <>
            <h1 style={{ fontSize: 20, marginBottom: 8 }}>This link can&apos;t be used</h1>
            <p role="alert" style={{ color: "var(--muted, #555)" }}>{message}</p>
          </>
        ) : (
          <p>Opening your onboarding…</p>
        )}
      </div>
    </main>
  );
}
