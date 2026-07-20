"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export default function ChangePasswordForm() {
  const [oldPwd,     setOldPwd]     = useState("");
  const [newPwd,     setNewPwd]     = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [showOld,    setShowOld]    = useState(false);
  const [showNew,    setShowNew]    = useState(false);
  const [showCnf,    setShowCnf]    = useState(false);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState("");
  const [success,    setSuccess]    = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setSuccess(false);
    if (!oldPwd)               { setError("Enter your current password."); return; }
    if (!newPwd)               { setError("Enter a new password."); return; }
    if (newPwd !== confirmPwd) { setError("New passwords do not match."); return; }
    if (newPwd === oldPwd)     { setError("New password must differ from the current one."); return; }
    setLoading(true);
    try {
      await clientApi.post(API.auth.changePassword, { old_password: oldPwd, new_password: newPwd, confirm_password: confirmPwd });
      setSuccess(true);
      setOldPwd(""); setNewPwd(""); setConfirmPwd("");
    } catch (err) {
      const { message } = err as { message: string };
      setError(message || "Failed to change password. Please try again.");
    } finally { setLoading(false); }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      {success && <div className="alert alert-success mb-3"><i className="ti ti-circle-check" /> Password changed successfully.</div>}
      {error   && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /> {error}</div>}

      {/* Current password */}
      <div className="field-group">
        <label className="field-label" htmlFor="cp-old">Current password</label>
        <div className="relative">
          <input id="cp-old" type={showOld ? "text" : "password"} className="field-input pr-[42px]"
            placeholder="Current password" value={oldPwd} onChange={e => setOldPwd(e.target.value)}
            required autoComplete="current-password" suppressHydrationWarning />
          <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
            onClick={() => setShowOld(v => !v)} suppressHydrationWarning>
            <i className={`ti ${showOld ? "ti-eye-off" : "ti-eye"}`} />
          </button>
        </div>
      </div>

      {/* New password */}
      <div className="field-group">
        <label className="field-label" htmlFor="cp-new">New password</label>
        <div className="relative">
          <input id="cp-new" type={showNew ? "text" : "password"} className="field-input pr-[42px]"
            placeholder="New password" value={newPwd} onChange={e => setNewPwd(e.target.value)}
            required autoComplete="new-password" suppressHydrationWarning />
          <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
            onClick={() => setShowNew(v => !v)} suppressHydrationWarning>
            <i className={`ti ${showNew ? "ti-eye-off" : "ti-eye"}`} />
          </button>
        </div>
      </div>

      {/* Confirm new password */}
      <div className="field-group">
        <label className="field-label" htmlFor="cp-confirm">Confirm new password</label>
        <div className="relative">
          <input id="cp-confirm" type={showCnf ? "text" : "password"} className="field-input pr-[42px]"
            placeholder="Confirm new password" value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)}
            required autoComplete="new-password" suppressHydrationWarning />
          <button type="button" tabIndex={-1} className="absolute right-2.5 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer p-1 text-[var(--outline)]"
            onClick={() => setShowCnf(v => !v)} suppressHydrationWarning>
            <i className={`ti ${showCnf ? "ti-eye-off" : "ti-eye"}`} />
          </button>
        </div>
      </div>

      <button type="submit" className="btn btn-filled w-full" style={{ marginTop: 8 }} disabled={loading} suppressHydrationWarning>
        {loading
          ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Updating…</>
          : <><i className="ti ti-lock" /> Update password</>
        }
      </button>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </form>
  );
}
