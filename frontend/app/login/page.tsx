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
      onboarding_status: string;
      assessment_status: string;
      can_manage_team: boolean;
      is_superuser: boolean;
    };
  };
}

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
    setLoading(true);
    setError("");
    try {
      const { data } = await clientApi.post<LoginApiResponse>(API.auth.login, { email, password });
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
        is_superuser:      d.user.is_superuser ?? false,
      };
      saveAuth(user);
      resetSessionExpired();
      let dest = "/dashboard";
      if (user.onboarding_status !== "complete") dest = "/onboarding";
      // Managers get auto-assigned default assessments the same as any new
      // employee (no role distinction on the backend), but the pre-onboarding
      // assessment portal isn't meant for them — skip it here too, matching
      // the same exemption in proxy.ts.
      else if (user.assessment_status === "pending" && !user.can_manage_team) dest = "/onboarding/assessments";
      router.push(dest);
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page-root">
      <div className="login-layout">

        {/* Left panel — decorative image, hidden on mobile */}
        <div className="login-image-panel">
          <Image
            src="/login.jpg"
            alt="Royal HRMS"
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
                src="/logo.png"
                alt="Royal HRMS"
                width={240}
                height={160}
                style={{ width: 240, height: "auto" }}
              />
            </div>

            <h2 className="login-title">Welcome back</h2>
            <p className="login-subtitle">Sign in to your Royal HRMS account</p>

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
              Protected by Royal HRMS · Enterprise SSO available
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
