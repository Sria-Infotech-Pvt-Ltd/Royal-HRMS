"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { PlatformAdminInfo } from "@/types/platformAdmin";

export default function MyAccountPage() {
  const router = useRouter();
  const { data: me } = useFetch<PlatformAdminInfo>(API.platformAdmin.me, platformAdminApi);

  const [oldPwd,     setOldPwd]     = useState("");
  const [newPwd,     setNewPwd]     = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [showOld,    setShowOld]    = useState(false);
  const [showNew,    setShowNew]    = useState(false);
  const [showCnf,    setShowCnf]    = useState(false);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!oldPwd)               { setError("Enter your current password."); return; }
    if (!newPwd)               { setError("Enter a new password."); return; }
    if (newPwd !== confirmPwd) { setError("New passwords do not match."); return; }
    if (newPwd === oldPwd)     { setError("New password must differ from the current one."); return; }
    setLoading(true);
    try {
      await platformAdminApi.post(API.platformAdmin.changePassword, {
        old_password: oldPwd, new_password: newPwd, confirm_password: confirmPwd,
      });
      // The backend clears this session's cookies as part of a successful
      // change (same pattern as the tenant side) — a fresh login is
      // required either way, so redirect straight there.
      router.push("/platform-admin/login");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to change password. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: "32px 24px" }}>
      <a href="/platform-admin/settings" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12.5, marginBottom: 12 }}>
        <i className="ti ti-arrow-left" /> Settings
      </a>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>My Account</h1>
      {me && <p className="text-muted" style={{ fontSize: 13, marginBottom: 24 }}>{me.full_name} · {me.email}</p>}

      {/* Page is full-width; the form itself stays at a readable size. */}
      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-body">
          <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Change password</h2>
          <form onSubmit={handleSubmit} noValidate>
            {error && (
              <div className="alert alert-warn mb-16">
                <i className="ti ti-alert-circle" /> {error}
              </div>
            )}

            <div className="field-group">
              <label className="field-label" htmlFor="pa-cp-old">Current password</label>
              <div className="relative">
                <input id="pa-cp-old" type={showOld ? "text" : "password"} className="field-input pr-[42px]"
                  value={oldPwd} onChange={e => setOldPwd(e.target.value)}
                  required autoComplete="current-password" suppressHydrationWarning />
                <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
                  onClick={() => setShowOld(v => !v)} suppressHydrationWarning>
                  <i className={`ti ${showOld ? "ti-eye-off" : "ti-eye"}`} />
                </button>
              </div>
            </div>

            <div className="field-group">
              <label className="field-label" htmlFor="pa-cp-new">New password</label>
              <div className="relative">
                <input id="pa-cp-new" type={showNew ? "text" : "password"} className="field-input pr-[42px]"
                  value={newPwd} onChange={e => setNewPwd(e.target.value)}
                  required autoComplete="new-password" suppressHydrationWarning />
                <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
                  onClick={() => setShowNew(v => !v)} suppressHydrationWarning>
                  <i className={`ti ${showNew ? "ti-eye-off" : "ti-eye"}`} />
                </button>
              </div>
            </div>

            <div className="field-group">
              <label className="field-label" htmlFor="pa-cp-confirm">Confirm new password</label>
              <div className="relative">
                <input id="pa-cp-confirm" type={showCnf ? "text" : "password"} className="field-input pr-[42px]"
                  value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)}
                  required autoComplete="new-password" suppressHydrationWarning />
                <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
                  onClick={() => setShowCnf(v => !v)} suppressHydrationWarning>
                  <i className={`ti ${showCnf ? "ti-eye-off" : "ti-eye"}`} />
                </button>
              </div>
            </div>

            <button type="submit" className="btn btn-filled" style={{ marginTop: 8 }} disabled={loading} suppressHydrationWarning>
              {loading ? (<><i className="ti ti-loader-2 spin" /> Updating…</>) : (<><i className="ti ti-lock" /> Update password</>)}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
