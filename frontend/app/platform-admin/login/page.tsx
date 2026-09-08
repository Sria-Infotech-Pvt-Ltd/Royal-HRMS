"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

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

        {/* Left panel — same photo used on the tenant/employee login screen,
            for one consistent look across every login surface. No overlaid
            text or logo here, matching that page exactly. */}
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
