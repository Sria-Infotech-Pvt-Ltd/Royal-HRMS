"use client";

import { useRouter } from "next/navigation";
import { clearAuth, getStoredUser } from "@/lib/auth";
import ChangePasswordForm from "@/app/dashboard/profile/ChangePasswordForm";

export default function ChangePasswordPage() {
  const router = useRouter();

  function handleSuccess() {
    // The account's password was still the one generated at provisioning
    // time (or reset by an admin) — the backend already logged this session
    // out as part of the change, so clear the local signal cookies too and
    // send the user to sign in fresh with their new password.
    //
    // Company Code and Email are read here (before clearAuth wipes the user
    // cookie) purely as a convenience so the employee doesn't have to retype
    // two non-secret identifiers they just used seconds ago — carried only
    // as plain query params on the /login redirect, never the password
    // itself, and never written to any storage. login/page.tsx reads them
    // once on mount and immediately strips them from the URL.
    const user = getStoredUser();
    clearAuth();
    const params = new URLSearchParams();
    if (user?.companyCode) params.set("company_code", user.companyCode);
    if (user?.email)       params.set("email", user.email);
    const qs = params.toString();
    router.push(qs ? `/login?${qs}` : "/login");
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div className="card" style={{ width: "100%", maxWidth: 440 }}>
        <div className="card-body">
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <div
              style={{
                width: 48, height: 48, borderRadius: "50%", background: "var(--primary-container)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
              }}
            >
              <i className="ti ti-lock" style={{ fontSize: 22, color: "var(--primary)" }} />
            </div>
            <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Set a new password</h1>
            <p style={{ fontSize: 13, color: "var(--on-variant)" }}>
              You&apos;re signed in with a temporary password. Choose a new one to continue.
            </p>
          </div>
          <ChangePasswordForm onSuccess={handleSuccess} />
        </div>
      </div>
    </div>
  );
}
