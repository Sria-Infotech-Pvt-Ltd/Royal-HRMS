"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

const FEATURES = [
  { icon: "ti-building", text: "Provision a new company in minutes, fully isolated from every other one" },
  { icon: "ti-shield-check", text: "Every company's data lives in its own schema — no admin here can see inside one" },
  { icon: "ti-chart-bar", text: "Real usage, not just registry counts — see which companies are actually active" },
];

export default function PlatformAdminLoginPage() {
  const router = useRouter();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await platformAdminApi.post(API.platformAdmin.login, { email, password });
      router.push("/platform-admin");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Login failed. Please check your credentials.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page-root">
      <div className="login-layout">

        {/* Left panel — gradient brand identity, matching the platform-admin dashboard's hero */}
        <div className="login-brand-panel">
          <i
            className="ti ti-shield-lock"
            style={{ position: "absolute", right: -30, bottom: -40, fontSize: 280, opacity: 0.08 }}
            aria-hidden
          />
          <div style={{ position: "relative", maxWidth: 380 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 32 }}>
              <div
                style={{
                  width: 40, height: 40, borderRadius: 10, background: "rgba(255,255,255,0.14)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}
              >
                <i className="ti ti-shield-lock" style={{ fontSize: 20, color: "#fff" }} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.2 }}>Royal HRMS</div>
                <div style={{ fontSize: 11.5, opacity: 0.7 }}>Platform Admin</div>
              </div>
            </div>

            <h1 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.25, marginBottom: 12 }}>
              One console for every company you run.
            </h1>
            <p style={{ fontSize: 14, opacity: 0.8, lineHeight: 1.6, marginBottom: 32 }}>
              Create companies, manage platform admins, and monitor usage across every
              tenant — from a single, isolated operator account.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {FEATURES.map(f => (
                <div key={f.icon} className="pa-login-feature">
                  <i className={`ti ${f.icon}`} />
                  <span>{f.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — sign-in form */}
        <div className="login-form-panel">
          <div className="login-form-inner">
            <div className="login-brand-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/logo.png"
                alt="Royal HRMS"
                width={240}
                height={160}
                style={{ width: 200, height: "auto", maxHeight: 90, objectFit: "contain" }}
              />
            </div>

            <h2 className="login-title">Sign in</h2>
            <p className="login-subtitle">Internal access — create and manage companies.</p>

            {error && (
              <div className="login-error-banner">
                <span>⚠</span> {error}
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate>
              <div className="login-field">
                <label htmlFor="pa-email" className="login-label">Email</label>
                <input
                  id="pa-email"
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

              <div className="login-field-pwd">
                <div className="login-label-row">
                  <label htmlFor="pa-password" className="login-label">Password</label>
                  <a href="/platform-admin/forgot-password" className="login-forgot-btn">Forgot password?</a>
                </div>
                <input
                  id="pa-password"
                  type="password"
                  className="login-input"
                  placeholder="Enter your password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onFocus={() => setError("")}
                  required
                  autoComplete="current-password"
                  suppressHydrationWarning
                />
              </div>

              <button type="submit" className="login-submit-btn" disabled={loading} suppressHydrationWarning>
                {loading && <Spinner />}
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <p className="login-footer-text">
              Not a platform operator? <a href="/login">Go to company sign-in</a>
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
