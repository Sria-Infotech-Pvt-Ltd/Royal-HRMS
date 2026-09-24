"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import clientApi, { resetSessionExpired } from "@/lib/clientApi";
import { saveAuth } from "@/lib/auth";
import type { UserInfo } from "@/lib/auth";
import ForgotPasswordForm from "@/components/auth/ForgotPasswordForm";
import { API } from "@/lib/api/endpoints";

interface LoginApiResponse {
  status: string;
  message: string;
  data: {
    user: {
      id: string;
      email: string;
      full_name: string;
      role: string;
      branch: string;
      permissions: string[];
      must_change_password: boolean;
      onboarding_status: string;
      assessment_status: string;
      can_manage_team: boolean;
      can_manage_branch: boolean;
      is_superuser: boolean;
    };
  };
}

const BRAND_NAME = "Aira HRMS";
const BRAND_LOGO = "/logo-icon.png";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!email.trim()) { setError("Please enter your email address."); return; }
    if (!password) { setError("Please enter your password."); return; }
    setLoading(true);
    setError("");
    try {
      const { data } = await clientApi.post<LoginApiResponse>(API.auth.login, {
        email, password,
      });
      const d = data.data;
      const user: UserInfo = {
        userId: d.user.id,
        email: d.user.email,
        name: d.user.full_name,
        role: d.user.role,
        branch: d.user.branch ?? "",
        permissions: d.user.permissions ?? [],
        onboarding_status: d.user.onboarding_status ?? "complete",
        assessment_status: d.user.assessment_status ?? "complete",
        can_manage_team:   d.user.can_manage_team ?? false,
        can_manage_branch: d.user.can_manage_branch ?? false,
        is_superuser:      d.user.is_superuser ?? false,
      };
      saveAuth(user);
      resetSessionExpired();
      let dest = "/dashboard";
      // A temporary or admin-reset password must be replaced before anything
      // else — checked first, ahead of onboarding/assessments, matching the
      // same priority order enforced server-side in proxy.ts.
      if (d.user.must_change_password) dest = "/change-password";
      // Superusers are platform/IT-provisioned admin accounts, never a real
      // hire that came through the candidate pipeline — the onboarding wizard
      // (personal details, bank info, documents) doesn't apply to them, so
      // they always land on the dashboard regardless of onboarding_status.
      // Branch Admin is the same kind of administrative account (assigned at
      // branch-creation time, not hired through the candidate pipeline), so
      // it gets the same exemption.
      else if (user.onboarding_status !== "complete" && !user.is_superuser && !user.can_manage_branch) dest = "/onboarding";
      // Managers get auto-assigned default assessments the same as any new
      // employee (no role distinction on the backend), but the pre-onboarding
      // assessment portal isn't meant for them — skip it here too, matching
      // the same exemption in proxy.ts. Superusers and Branch Admin are
      // exempt for the same reason as the onboarding check above.
      else if (user.assessment_status === "pending" && !user.can_manage_team && !user.can_manage_branch && !user.is_superuser) dest = "/onboarding/assessments";
      router.push(dest);
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  const subtitle = `Sign in to your ${BRAND_NAME} account`;

  return (
    <div className="login-page-root">
      <div className="login-layout">

        {/* Left panel — decorative image, hidden on mobile */}
        <div className="login-image-panel">
          <Image
            src="/login.jpg"
            alt={BRAND_NAME}
            fill
            className="login-image"
            sizes="60vw"
            priority
          />
        </div>

        {/* Right panel — sign-in form */}
        <div className="login-form-panel">
          <div className="login-form-inner">

            {/* Brand logo */}
            <div className="login-brand-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={BRAND_LOGO}
                alt={BRAND_NAME}
                width={240}
                height={160}
                style={{ width: 240, height: "auto", maxHeight: 100, objectFit: "contain" }}
              />
            </div>

            <h2 className="login-title">Welcome back</h2>
            <p className="login-subtitle">{subtitle}</p>

            {/* Error banner */}
            {error && (
              <div className="login-error-banner">
                <span>⚠</span> {error}
              </div>
            )}

            {showForgot ? (
              <ForgotPasswordForm
                onBack={() => { setShowForgot(false); setForgotSent(false); }}
                sent={forgotSent}
                onSend={() => setForgotSent(true)}
              />
            ) : (
              <form onSubmit={handleSubmit} noValidate>

                {/* Email field */}
                <div className="login-field">
                  <label htmlFor="login-email" className="login-label">
                    Email
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    className="login-input"
                    placeholder="you@company.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    onFocus={() => setError("")}
                    required
                    autoComplete="email"
                    suppressHydrationWarning
                  />
                </div>

                {/* Password field */}
                <div className="login-field-pwd">
                  <div className="login-label-row">
                    <label htmlFor="login-password" className="login-label">
                      Password
                    </label>
                    <button
                      type="button"
                      className="login-forgot-btn"
                      onClick={() => setShowForgot(true)}
                      suppressHydrationWarning
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="login-pwd-wrap">
                    <input
                      id="login-password"
                      type={showPwd ? "text" : "password"}
                      className="login-input login-input-pwd"
                      placeholder="Enter your password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      onFocus={() => setError("")}
                      required
                      autoComplete="current-password"
                      suppressHydrationWarning
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      aria-label={showPwd ? "Hide password" : "Show password"}
                      className="login-pwd-toggle"
                      onClick={() => setShowPwd(v => !v)}
                      suppressHydrationWarning
                    >
                      {showPwd ? <i className="ti ti-eye-off" /> : <i className="ti ti-eye" />}
                    </button>
                  </div>
                </div>

                {/* Sign in button */}
                <button
                  type="submit"
                  className="login-submit-btn"
                  disabled={loading}
                  suppressHydrationWarning
                >
                  {loading && <Spinner />}
                  {loading ? "Signing in…" : "Sign in"}
                </button>

              </form>
            )}

            <p className="login-footer-text">
              Protected by {BRAND_NAME} · Enterprise SSO available
            </p>

          </div>
        </div>

      </div>
    </div>
  );
}

function Spinner() {
  return <span className="login-spinner" />;
}
