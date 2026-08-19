"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

type Step = "email" | "otp" | "reset" | "done";

export default function PlatformAdminForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function sendOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) { setError("Enter your email address."); return; }
    setError(""); setLoading(true);
    try {
      await platformAdminApi.post(API.platformAdmin.forgotPassword, { email: email.trim() });
      setStep("otp");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Unable to send OTP. Please try again.";
      setError(message);
    } finally { setLoading(false); }
  }

  async function verifyOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!otp.trim()) { setError("Enter the OTP."); return; }
    setError(""); setLoading(true);
    try {
      const { data } = await platformAdminApi.post<{ data: { reset_token: string } }>(
        API.platformAdmin.verifyOtp, { email: email.trim(), otp: otp.trim() },
      );
      setResetToken(data.data.reset_token);
      setStep("reset");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Invalid or expired OTP.";
      setError(message);
    } finally { setLoading(false); }
  }

  async function resetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!newPwd)               { setError("Enter your new password."); return; }
    if (newPwd !== confirmPwd) { setError("Passwords do not match."); return; }
    setError(""); setLoading(true);
    try {
      await platformAdminApi.post(API.platformAdmin.resetPassword, {
        reset_token: resetToken, new_password: newPwd, confirm_password: confirmPwd,
      });
      setStep("done");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Password reset failed. Please try again.";
      setError(message);
    } finally { setLoading(false); }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-low)" }}>
      <div className="card" style={{ width: 380, maxWidth: "92vw" }}>
        <div className="card-body">
          {step !== "done" && (
            <a href="/platform-admin/login" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12.5, marginBottom: 16 }}>
              <i className="ti ti-arrow-left" /> Back to sign in
            </a>
          )}

          {error && (
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" /><div>{error}</div>
            </div>
          )}

          {step === "email" && (
            <>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Reset your password</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 20 }}>
                Enter your registered email and we&apos;ll send you a one-time code.
              </p>
              <form onSubmit={sendOtp} noValidate>
                <div className="field-group" style={{ marginBottom: 16 }}>
                  <label htmlFor="fp-email" className="field-label">Email</label>
                  <input id="fp-email" type="email" className="field-input" value={email}
                    onChange={e => setEmail(e.target.value)} required autoFocus suppressHydrationWarning />
                </div>
                <button type="submit" className="btn btn-filled" style={{ width: "100%", justifyContent: "center" }} disabled={loading} suppressHydrationWarning>
                  {loading ? (<><i className="ti ti-loader-2 spin" /> Sending…</>) : "Send OTP"}
                </button>
              </form>
            </>
          )}

          {step === "otp" && (
            <>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Enter OTP</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 20 }}>
                A 6-digit code was sent to <strong>{email}</strong>.
              </p>
              <form onSubmit={verifyOtp} noValidate>
                <div className="field-group" style={{ marginBottom: 16 }}>
                  <label htmlFor="fp-otp" className="field-label">One-time code</label>
                  <input id="fp-otp" type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6}
                    className="field-input" value={otp}
                    onChange={e => setOtp(e.target.value.replace(/\D/g, ""))} required autoFocus suppressHydrationWarning />
                </div>
                <button type="submit" className="btn btn-filled" style={{ width: "100%", justifyContent: "center" }} disabled={loading} suppressHydrationWarning>
                  {loading ? (<><i className="ti ti-loader-2 spin" /> Verifying…</>) : "Verify OTP"}
                </button>
                <button type="button" className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
                  onClick={() => { setStep("email"); setError(""); setOtp(""); }} suppressHydrationWarning>
                  Resend code
                </button>
              </form>
            </>
          )}

          {step === "reset" && (
            <>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Set new password</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 20 }}>
                Choose a strong password for your account.
              </p>
              <form onSubmit={resetPassword} noValidate>
                <div className="field-group" style={{ marginBottom: 14 }}>
                  <label htmlFor="fp-new" className="field-label">New password</label>
                  <input id="fp-new" type="password" className="field-input" value={newPwd}
                    onChange={e => setNewPwd(e.target.value)} required autoFocus suppressHydrationWarning />
                </div>
                <div className="field-group" style={{ marginBottom: 16 }}>
                  <label htmlFor="fp-confirm" className="field-label">Confirm password</label>
                  <input id="fp-confirm" type="password" className="field-input" value={confirmPwd}
                    onChange={e => setConfirmPwd(e.target.value)} required suppressHydrationWarning />
                </div>
                <button type="submit" className="btn btn-filled" style={{ width: "100%", justifyContent: "center" }} disabled={loading} suppressHydrationWarning>
                  {loading ? (<><i className="ti ti-loader-2 spin" /> Resetting…</>) : "Reset password"}
                </button>
              </form>
            </>
          )}

          {step === "done" && (
            <div style={{ textAlign: "center" }}>
              <i className="ti ti-circle-check" style={{ fontSize: 40, color: "var(--success)", display: "block", marginBottom: 12 }} />
              <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 20 }}>
                Your password has been reset. You can now sign in with your new password.
              </p>
              <button type="button" className="btn btn-filled" style={{ width: "100%", justifyContent: "center" }}
                onClick={() => router.push("/platform-admin/login")} suppressHydrationWarning>
                Back to sign in
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
