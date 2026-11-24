"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useT } from "@/hooks/useI18n";

type ForgotStep = "email" | "otp" | "reset" | "done";

// Matches the server (OTP_RESEND_COOLDOWN_SECONDS): a second request inside this window is answered without sending a new code.
const RESEND_COOLDOWN_SECONDS = 60;

function Spinner() {
  return (
    <span style={{
      width: "16px", height: "16px",
      borderRadius: "50%",
      border: "2px solid rgba(255,255,255,0.35)",
      borderTopColor: "#fff",
      display: "inline-block",
      flexShrink: 0,
      animation: "spin 0.7s linear infinite",
    }} />
  );
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "8px",
      padding: "10px 14px",
      borderRadius: "var(--radius)",
      background: "var(--error-c)",
      color: "var(--error)",
      border: "1px solid #ffb3ae",
      fontSize: "13px",
      marginBottom: "16px",
    }}>
      <span>⚠</span> {msg}
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "13px",
  fontWeight: 500,
  marginBottom: "6px",
  color: "var(--on-variant)",
};

const fieldStyle: React.CSSProperties = { marginBottom: "14px" };

export default function ForgotPasswordForm({
  onBack,
}: {
  onBack: () => void;
  sent: boolean;
  onSend: () => void;
}) {
  const t = useT();
  const [step,        setStep]        = useState<ForgotStep>("email");
  const [emailVal,    setEmailVal]    = useState("");
  const [otp,         setOtp]         = useState("");
  const [resetToken,  setResetToken]  = useState("");
  const [newPwd,      setNewPwd]      = useState("");
  const [confirmPwd,  setConfirmPwd]  = useState("");
  const [showNew,     setShowNew]     = useState(false);
  const [showConf,    setShowConf]    = useState(false);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState("");
  // Seconds before "Resend code" works again: a second request would cancel the code already on its way.
  const [resendIn,    setResendIn]    = useState(0);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = window.setTimeout(() => setResendIn(seconds => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendIn]);

  async function sendForgot(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!emailVal.trim()) { setError(t("Please enter your email address.")); return; }
    setLoading(true); setError("");
    try {
      await clientApi.post(API.auth.forgotPassword, { email: emailVal.trim() });
      setStep("otp");
      setResendIn(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || t("Unable to send OTP. Please try again."));
    } finally { setLoading(false); }
  }

  async function resendOtp() {
    setLoading(true); setError("");
    try {
      await clientApi.post(API.auth.forgotPassword, { email: emailVal.trim() });
      setOtp("");
      setResendIn(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || t("Unable to resend OTP. Please try again."));
    } finally { setLoading(false); }
  }

  async function verifyOtp(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!otp.trim()) { setError(t("Please enter the OTP.")); return; }
    setLoading(true); setError("");
    try {
      const { data } = await clientApi.post<{ data?: { reset_token?: string }; reset_token?: string }>(
        API.auth.verifyOtp, { email: emailVal.trim(), otp: otp.trim() },
      );
      const token = data?.data?.reset_token ?? (data as Record<string, unknown>).reset_token as string ?? "";
      setResetToken(token);
      setStep("reset");
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || t("Invalid or expired OTP."));
    } finally { setLoading(false); }
  }

  async function resetPassword(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!newPwd)              { setError(t("Enter your new password.")); return; }
    if (newPwd !== confirmPwd) { setError(t("Passwords do not match.")); return; }
    setLoading(true); setError("");
    try {
      await clientApi.post(API.auth.resetPassword, {
        reset_token: resetToken, new_password: newPwd, confirm_password: confirmPwd,
      });
      setStep("done");
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || t("Password reset failed. Please try again."));
    } finally { setLoading(false); }
  }

  /* ── Done state ── */
  if (step === "done") {
    return (
      <div style={{ textAlign: "center", padding: "8px 0" }}>
        <div style={{ fontSize: "40px", marginBottom: "14px" }}>✅</div>
        <p style={{ fontSize: "13px", color: "var(--on-variant)", lineHeight: 1.6, marginBottom: "16px" }}>
          {t("Your password has been reset. You can now sign in with your new password.")}
        </p>
        <button type="button" className="login-submit-btn" onClick={onBack} suppressHydrationWarning>
          {t("Back to Sign In")}
        </button>
      </div>
    );
  }

  /* ── Multi-step form ── */
  return (
    <div>
      {/* Back navigation */}
      <button type="button" onClick={onBack} className="forgot-back-btn" suppressHydrationWarning>
        <span className="forgot-back-arrow">←</span>
        {t("Back to Sign In")}
      </button>

      {/* ── Step: email ── */}
      {step === "email" && (
        <>
          <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--on-bg)", marginBottom: "6px", letterSpacing: "-0.01em" }}>
            {t("Reset your password")}
          </h3>
          <p style={{ fontSize: "13px", color: "var(--on-variant)", marginBottom: "20px", lineHeight: 1.6 }}>
            {t("Enter your registered email and we'll send you a one-time code.")}
          </p>
          {error && <ErrorBanner msg={error} />}
          <form onSubmit={sendForgot} noValidate>
            <div style={fieldStyle}>
              <label htmlFor="forgot-email" style={labelStyle}>{t("Email")}</label>
              <input
                id="forgot-email"
                type="email"
                className="login-input"
                placeholder={t("you@company.com")}
                value={emailVal}
                onChange={e => setEmailVal(e.target.value)}
                required
                autoComplete="email"
                autoFocus
                suppressHydrationWarning
              />
            </div>
            <button type="submit" className="login-submit-btn" disabled={loading} suppressHydrationWarning>
              {loading && <Spinner />}
              {loading ? t("Sending…") : t("Send OTP")}
            </button>
          </form>
        </>
      )}

      {/* ── Step: otp ── */}
      {step === "otp" && (
        <>
          <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--on-bg)", marginBottom: "6px", letterSpacing: "-0.01em" }}>
            {t("Enter OTP")}
          </h3>
          <p style={{ fontSize: "13px", color: "var(--on-variant)", marginBottom: "20px", lineHeight: 1.6 }}>
            {t("A 6-digit code was sent to")} <strong>{emailVal}</strong>.
          </p>
          {error && <ErrorBanner msg={error} />}
          <form onSubmit={verifyOtp} noValidate>
            <div style={fieldStyle}>
              <label htmlFor="otp-input" style={labelStyle}>{t("One-time code")}</label>
              <input
                id="otp-input"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                className="login-input"
                placeholder="123456"
                value={otp}
                onChange={e => setOtp(e.target.value.replace(/\D/g, ""))}
                required
                autoFocus
                suppressHydrationWarning
              />
            </div>
            <button type="submit" className="login-submit-btn" disabled={loading} suppressHydrationWarning>
              {loading && <Spinner />}
              {loading ? t("Verifying…") : t("Verify OTP")}
            </button>
            <button
              type="button"
              disabled={loading || resendIn > 0}
              style={{ display: "block", marginTop: "10px", fontSize: "13px", color: resendIn > 0 ? "var(--on-variant)" : "var(--primary)", background: "none", border: "none", cursor: resendIn > 0 ? "not-allowed" : "pointer", fontFamily: "inherit", padding: 0 }}
              onClick={resendOtp}
              suppressHydrationWarning
            >
              {resendIn > 0 ? t("Resend code in {seconds}s (use the latest email)", { seconds: resendIn }) : t("Resend code")}
            </button>
            <button
              type="button"
              disabled={loading}
              style={{ display: "block", marginTop: "6px", fontSize: "13px", color: "var(--on-variant)", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit", padding: 0 }}
              onClick={() => { setStep("email"); setError(""); setOtp(""); }}
              suppressHydrationWarning
            >
              {t("Change email address")}
            </button>
          </form>
        </>
      )}

      {/* ── Step: reset ── */}
      {step === "reset" && (
        <>
          <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--on-bg)", marginBottom: "6px", letterSpacing: "-0.01em" }}>
            {t("Set new password")}
          </h3>
          <p style={{ fontSize: "13px", color: "var(--on-variant)", marginBottom: "20px", lineHeight: 1.6 }}>
            {t("Choose a strong password for your account.")}
          </p>
          {error && <ErrorBanner msg={error} />}
          <form onSubmit={resetPassword} noValidate>
            <div style={fieldStyle}>
              <label htmlFor="new-pwd" style={labelStyle}>{t("New password")}</label>
              <div style={{ position: "relative" }}>
                <input
                  id="new-pwd"
                  type={showNew ? "text" : "password"}
                  className="login-input login-input-pwd"
                  placeholder={t("New password")}
                  value={newPwd}
                  onChange={e => setNewPwd(e.target.value)}
                  required
                  autoFocus
                  suppressHydrationWarning
                />
                <button
                  type="button"
                  tabIndex={-1}
                  style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", fontSize: "18px", lineHeight: 1, padding: "4px", color: "var(--outline)" }}
                  onClick={() => setShowNew(v => !v)}
                  suppressHydrationWarning
                >
                  {showNew ? "🙈" : "👁️"}
                </button>
              </div>
            </div>
            <div style={fieldStyle}>
              <label htmlFor="confirm-pwd" style={labelStyle}>{t("Confirm password")}</label>
              <div style={{ position: "relative" }}>
                <input
                  id="confirm-pwd"
                  type={showConf ? "text" : "password"}
                  className="login-input login-input-pwd"
                  placeholder={t("Confirm password")}
                  value={confirmPwd}
                  onChange={e => setConfirmPwd(e.target.value)}
                  required
                  suppressHydrationWarning
                />
                <button
                  type="button"
                  tabIndex={-1}
                  style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", fontSize: "18px", lineHeight: 1, padding: "4px", color: "var(--outline)" }}
                  onClick={() => setShowConf(v => !v)}
                  suppressHydrationWarning
                >
                  {showConf ? "🙈" : "👁️"}
                </button>
              </div>
            </div>
            <button type="submit" className="login-submit-btn" disabled={loading} suppressHydrationWarning>
              {loading && <Spinner />}
              {loading ? t("Resetting…") : t("Reset password")}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
