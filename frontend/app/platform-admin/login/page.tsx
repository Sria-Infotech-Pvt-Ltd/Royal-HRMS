"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-low)" }}>
      <div className="card" style={{ width: 380, maxWidth: "92vw" }}>
        <div className="card-body">
          <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Platform Admin</h1>
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 20 }}>
            Internal access — create and manage companies.
          </p>

          {error && (
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="field-group" style={{ marginBottom: 14 }}>
              <label htmlFor="pa-email" className="field-label">Email</label>
              <input
                id="pa-email"
                type="email"
                className="field-input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onFocus={() => setError("")}
                required
                autoComplete="email"
                suppressHydrationWarning
              />
            </div>

            <div className="field-group" style={{ marginBottom: 20 }}>
              <label htmlFor="pa-password" className="field-label">Password</label>
              <input
                id="pa-password"
                type="password"
                className="field-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onFocus={() => setError("")}
                required
                autoComplete="current-password"
                suppressHydrationWarning
              />
            </div>

            <button type="submit" className="btn btn-filled" style={{ width: "100%", justifyContent: "center" }} disabled={loading} suppressHydrationWarning>
              {loading ? (<><i className="ti ti-loader-2 spin" /> Signing in…</>) : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
