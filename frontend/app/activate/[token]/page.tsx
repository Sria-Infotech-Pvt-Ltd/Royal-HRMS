"use client";

// New-hire account activation — the landing page for the single-use invite
// link emailed at hire completion (see apps.accounts.utils.send_activation_invite
// / views.auth.InviteCheckView on the backend). Replaces the old plaintext-
// temporary-password email: nobody ever sees a password here, the new hire
// sets their own via the same reset-password endpoint the forgot-password
// flow already uses (a PasswordResetToken is a PasswordResetToken regardless
// of purpose).
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

type CheckState = "loading" | "valid" | "invalid";

interface InviteCheckData {
  full_name: string;
  email: string;
}

const RULES: { key: string; label: string; test: (pwd: string) => boolean }[] = [
  { key: "length", label: "At least 8 characters", test: pwd => pwd.length >= 8 },
  { key: "letter", label: "Contains a letter", test: pwd => /[A-Za-z]/.test(pwd) },
  { key: "number", label: "Contains a number", test: pwd => /\d/.test(pwd) },
  { key: "notAllDigits", label: "Not entirely numeric", test: pwd => pwd.length > 0 && !/^\d+$/.test(pwd) },
];

function strengthScore(pwd: string): number {
  if (!pwd) return 0;
  let score = 0;
  if (pwd.length >= 8) score++;
  if (pwd.length >= 12) score++;
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
  if (/\d/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  return Math.min(score, 4);
}

const STRENGTH_LABEL = ["Very weak", "Weak", "Fair", "Good", "Strong"];
const STRENGTH_COLOR = ["var(--error)", "var(--error)", "var(--warn)", "var(--info)", "var(--success)"];

export default function ActivatePage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [checkState, setCheckState] = useState<CheckState>("loading");
  const [checkError, setCheckError] = useState("");
  const [invitee, setInvitee] = useState<InviteCheckData | null>(null);

  const [step, setStep] = useState<"welcome" | "password" | "done">("welcome");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) return;
    clientApi
      .get<{ data: InviteCheckData }>(API.auth.inviteCheck(token))
      .then(r => {
        setInvitee(r.data.data);
        setCheckState("valid");
      })
      .catch((err: unknown) => {
        const msg = (err as { message?: string })?.message
          ?? "This activation link is invalid or has expired.";
        setCheckError(msg);
        setCheckState("invalid");
      });
  }, [token]);

  const score = strengthScore(password);
  const rulesPassed = RULES.every(r => r.test(password));
  const passwordsMatch = password.length > 0 && password === confirm;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError("");
    if (!rulesPassed) { setSubmitError("Please satisfy every password rule below."); return; }
    if (!passwordsMatch) { setSubmitError("Passwords do not match."); return; }

    setSubmitting(true);
    try {
      await clientApi.post(API.auth.resetPassword, {
        reset_token: token,
        new_password: password,
        confirm_password: confirm,
      });
      setStep("done");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Could not set your password. Please try again.";
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  const firstName = (invitee?.full_name || "").split(" ")[0] || "there";

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, background: "var(--bg)" }}>
      <div className="card" style={{ width: "100%", maxWidth: 460 }}>
        <div className="card-body" style={{ padding: 32 }}>
          {checkState === "loading" && (
            <div style={{ textAlign: "center", padding: "24px 0" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 28, animation: "spin 1s linear infinite", color: "var(--primary)" }} />
              <p style={{ marginTop: 12, color: "var(--on-variant)", fontSize: 13 }}>Checking your invite…</p>
            </div>
          )}

          {checkState === "invalid" && (
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 48, height: 48, borderRadius: "50%", background: "var(--error-c)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
              }}>
                <i className="ti ti-link-off" style={{ fontSize: 22, color: "var(--error)" }} />
              </div>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>This link isn&apos;t valid</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", lineHeight: 1.6 }}>{checkError}</p>
              <p style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 16 }}>
                Ask HR to resend your activation invite, or{" "}
                <a href="/login" style={{ color: "var(--primary)" }}>go to login</a>.
              </p>
            </div>
          )}

          {checkState === "valid" && step === "welcome" && (
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 48, height: 48, borderRadius: "50%", background: "var(--primary-container)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
              }}>
                <i className="ti ti-confetti" style={{ fontSize: 22, color: "var(--primary)" }} />
              </div>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Welcome, {firstName}!</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: 24 }}>
                Let&apos;s secure your account. You&apos;ll set your own password now — it takes about a minute.
                After that, you&apos;ll be guided through a short onboarding checklist.
              </p>
              <button className="btn btn-filled w-full" onClick={() => setStep("password")} suppressHydrationWarning>
                Get Started <i className="ti ti-arrow-right" />
              </button>
            </div>
          )}

          {checkState === "valid" && step === "password" && (
            <>
              <div style={{ textAlign: "center", marginBottom: 20 }}>
                <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Set your password</h1>
                <p style={{ fontSize: 13, color: "var(--on-variant)" }}>
                  Signing in as <strong>{invitee?.email}</strong>
                </p>
              </div>

              <form onSubmit={handleSubmit} noValidate>
                {submitError && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /> {submitError}</div>}

                <div className="field-group">
                  <label className="field-label" htmlFor="act-pwd">New password</label>
                  <div className="relative">
                    <input
                      id="act-pwd" type={showPwd ? "text" : "password"} className="field-input pr-[42px]"
                      placeholder="New password" value={password} onChange={e => setPassword(e.target.value)}
                      autoComplete="new-password" autoFocus suppressHydrationWarning
                    />
                    <button type="button" tabIndex={-1}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
                      onClick={() => setShowPwd(v => !v)} suppressHydrationWarning>
                      <i className={`ti ${showPwd ? "ti-eye-off" : "ti-eye"}`} />
                    </button>
                  </div>
                </div>

                {password.length > 0 && (
                  <div style={{ marginBottom: 12, marginTop: -4 }}>
                    <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
                      {[0, 1, 2, 3].map(i => (
                        <div key={i} style={{
                          flex: 1, height: 4, borderRadius: 2,
                          background: i < score ? STRENGTH_COLOR[score] : "var(--outline-v)",
                        }} />
                      ))}
                    </div>
                    <span style={{ fontSize: 11.5, color: STRENGTH_COLOR[score], fontWeight: 600 }}>
                      {STRENGTH_LABEL[score]}
                    </span>
                  </div>
                )}

                <div className="field-group">
                  <label className="field-label" htmlFor="act-confirm">Confirm password</label>
                  <div className="relative">
                    <input
                      id="act-confirm" type={showConfirm ? "text" : "password"} className="field-input pr-[42px]"
                      placeholder="Confirm password" value={confirm} onChange={e => setConfirm(e.target.value)}
                      autoComplete="new-password" suppressHydrationWarning
                    />
                    <button type="button" tabIndex={-1}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
                      onClick={() => setShowConfirm(v => !v)} suppressHydrationWarning>
                      <i className={`ti ${showConfirm ? "ti-eye-off" : "ti-eye"}`} />
                    </button>
                  </div>
                  {confirm.length > 0 && !passwordsMatch && (
                    <span className="field-error-msg">Passwords do not match.</span>
                  )}
                </div>

                <div style={{ margin: "8px 0 16px", padding: "10px 12px", background: "var(--bg-mid)", borderRadius: 8 }}>
                  {RULES.map(r => {
                    const passed = r.test(password);
                    return (
                      <div key={r.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, padding: "2px 0", color: passed ? "var(--success)" : "var(--on-variant)" }}>
                        <i className={`ti ${passed ? "ti-circle-check-filled" : "ti-circle"}`} style={{ fontSize: 14 }} />
                        {r.label}
                      </div>
                    );
                  })}
                </div>

                <button type="submit" className="btn btn-filled w-full" disabled={submitting} suppressHydrationWarning>
                  {submitting
                    ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Activating…</>
                    : <><i className="ti ti-shield-check" /> Activate my account</>
                  }
                </button>
              </form>
            </>
          )}

          {checkState === "valid" && step === "done" && (
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 48, height: 48, borderRadius: "50%", background: "var(--success-c)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
              }}>
                <i className="ti ti-circle-check" style={{ fontSize: 22, color: "var(--success)" }} />
              </div>
              <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>You&apos;re all set!</h1>
              <p style={{ fontSize: 13, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: 20 }}>
                Your account is active. Log in with your new password to start your onboarding checklist.
              </p>
              <button className="btn btn-filled w-full" onClick={() => router.push("/login")} suppressHydrationWarning>
                Go to Login <i className="ti ti-arrow-right" />
              </button>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
