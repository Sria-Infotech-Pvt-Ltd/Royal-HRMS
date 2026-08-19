"use client";

import { useEffect, useRef, useState } from "react";
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
      company_code: string;
      company_name: string;
      company_logo_url: string | null;
      company_brand_color: string;
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

interface BrandingResponse {
  data: { company_name: string; logo_url: string | null; brand_color: string };
}

const DEFAULT_BRAND_NAME = "Royal HRMS";
const DEFAULT_LOGO = "/logo.png";

export default function LoginPage() {
  const router = useRouter();
  const [companyCode, setCompanyCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  // Per-company white-labeling — swapped in once a valid company code is
  // known, either typed in below or auto-resolved from a company's own
  // custom domain (see the effect below). Falls back to the shared Royal
  // HRMS look whenever no company is resolved yet.
  const [brandName, setBrandName] = useState(DEFAULT_BRAND_NAME);
  const [brandLogoUrl, setBrandLogoUrl] = useState<string | null>(null);
  const [brandColor, setBrandColor] = useState("");
  const brandLookupTicket = useRef(0);

  // If this domain has been registered as a company's own custom domain
  // (platform admin sets Client.custom_domain), skip asking for a Company
  // ID at all — window.location.hostname is what the browser is actually
  // on, independent of anything the Next.js→Django proxy hop might do to
  // request headers along the way.
  useEffect(() => {
    const host = window.location.hostname;
    if (!host || host === "localhost") return;
    clientApi
      .get<{ data: { company_code: string } }>(`${API.auth.resolveDomain}?domain=${encodeURIComponent(host)}`)
      .then(res => setCompanyCode(res.data.data.company_code))
      .catch(() => {});
  }, []);

  // Debounced branding lookup as the Company ID field changes.
  useEffect(() => {
    const code = companyCode.trim();
    if (!code) {
      setBrandName(DEFAULT_BRAND_NAME);
      setBrandLogoUrl(null);
      setBrandColor("");
      return;
    }
    const ticket = ++brandLookupTicket.current;
    const timer = setTimeout(() => {
      clientApi
        .get<BrandingResponse>(API.auth.companyBranding(code))
        .then(res => {
          if (ticket !== brandLookupTicket.current) return;
          const b = res.data.data;
          setBrandName(b.company_name || DEFAULT_BRAND_NAME);
          setBrandLogoUrl(b.logo_url);
          setBrandColor(b.brand_color || "");
        })
        .catch(() => {
          if (ticket !== brandLookupTicket.current) return;
          setBrandName(DEFAULT_BRAND_NAME);
          setBrandLogoUrl(null);
          setBrandColor("");
        });
    }, 400);
    return () => clearTimeout(timer);
  }, [companyCode]);

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
        companyLogoUrl: d.user.company_logo_url ?? null,
        companyBrandColor: d.user.company_brand_color ?? "",
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

  const subtitle = `Sign in to your ${brandName} account`;

  return (
    <div
      className="login-page-root"
      // brandColor is user-configured per company (Company.brand_color) — a
      // CSS custom property has no dedicated key in React.CSSProperties, so
      // this cast is the standard way to set one; safe because the value is
      // validated server-side as a strict #rrggbb hex string before it's
      // ever stored (see CompanySerializer.validate_brand_color).
      style={brandColor ? ({ "--primary": brandColor } as React.CSSProperties) : undefined}
    >
      <div className="login-layout">

        {/* Left panel — decorative image, hidden on mobile */}
        <div className="login-image-panel">
          <Image
            src="/login.jpg"
            alt={brandName}
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
                src={brandLogoUrl || DEFAULT_LOGO}
                alt={brandName}
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
                initialCompanyCode={companyCode}
              />
            ) : (
              <form onSubmit={handleSubmit} noValidate>

                {/* Company code field — always required, for every role.
                    It's what tells the backend which tenant schema to check
                    for this email (see backend LoginSerializer/LoginView). */}
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

            <p className="login-footer-text">
              Protected by {brandName} · Enterprise SSO available
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
