"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
      company_code: string;
      company_name: string;
      email: string;
      full_name: string;
      role: string;
      branch: string;
      permissions: string[];
      onboarding_status: string;
      assessment_status: string;
      can_manage_team: boolean;
      can_manage_branch: boolean;
      is_superuser: boolean;
    };
  };
}

const PORTAL_COPY: Record<string, { title: string; subtitle: string }> = {
  hr:       { title: "HR & Admin Sign In", subtitle: "Access the HR administration portal" },
  employee: { title: "Employee Sign In",   subtitle: "Access your personal employee portal" },
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const portal = searchParams.get("portal");
  const copy = (portal && PORTAL_COPY[portal]) || { title: "Welcome back", subtitle: "Sign in to your Royal HRMS account" };
  const [companyCode, setCompanyCode] = useState("");
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
      const { data } = await clientApi.post<LoginApiResponse>(API.auth.login, {
        company_code: companyCode, email, password,
      });
      const d = data.data;
      const user: UserInfo = {
        userId: d.user.id,
        companyCode: d.user.company_code,
        companyName: d.user.company_name,
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
      // Superusers are platform/IT-provisioned admin accounts, never a real
      // hire that came through the candidate pipeline — the onboarding wizard
      // (personal details, bank info, documents) doesn't apply to them, so
      // they always land on the dashboard regardless of onboarding_status.
      if (user.onboarding_status !== "complete" && !user.is_superuser) dest = "/onboarding";
      // Managers get auto-assigned default assessments the same as any new
      // employee (no role distinction on the backend), but the pre-onboarding
      // assessment portal isn't meant for them — skip it here too, matching
      // the same exemption in proxy.ts. Superusers are exempt for the same
      // reason as the onboarding check above.
      else if (user.assessment_status === "pending" && !user.can_manage_team && !user.is_superuser) dest = "/onboarding/assessments";
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

            <h2 className="login-title">{copy.title}</h2>
            <p className="login-subtitle">{copy.subtitle}</p>

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

                {/* Company code field */}
                <div className="login-field">
                  <label htmlFor="login-company-code" className="login-label">
                    Company ID
                  </label>
                  <input
                    id="login-company-code"
                    type="text"
                    className="login-input"
                    placeholder="e.g. ROYALHRMS"
                    value={companyCode}
                    onChange={e => setCompanyCode(e.target.value)}
                    onFocus={() => setError("")}
                    required
                    autoComplete="organization"
                    suppressHydrationWarning
                  />
                </div>

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

            {portal && !showForgot && (
              <button
                type="button"
                className="login-forgot-btn"
                style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 4 }}
                onClick={() => router.push("/portal")}
              >
                <i className="ti ti-arrow-left" /> Not you? Choose a different portal
              </button>
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
