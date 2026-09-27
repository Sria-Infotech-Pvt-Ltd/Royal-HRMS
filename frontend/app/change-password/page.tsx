"use client";

import { useRouter } from "next/navigation";
import { clearAuth } from "@/lib/auth";
import ChangePasswordForm from "@/app/dashboard/profile/ChangePasswordForm";

export default function ChangePasswordPage() {
  const router = useRouter();

  function handleSuccess() {
    // The account's password was still the one generated at provisioning
    // time (or reset by an admin) — the backend already logged this session
    // out as part of the change, so clear the local signal cookies too and
    // send the user to sign in fresh with their new password.
    clearAuth();
    router.push("/login");
  }

  return (
    <div style={{ height: "100vh", overflowY: "auto", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
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
