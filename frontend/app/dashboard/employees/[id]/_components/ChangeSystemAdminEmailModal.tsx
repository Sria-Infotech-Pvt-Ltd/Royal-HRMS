"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";

interface Props {
  employeeId:   string;   // employee_id code, e.g. "RIS00001" — matches API.employees.detail
  employeeName: string;
  currentEmail: string;
  onClose:      () => void;
  /** Fired after a successful change so the parent can update the
   *  displayed email without a full page reload. */
  onChanged:    (newEmail: string) => void;
}

const EMAIL_RE = /^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

export default function ChangeSystemAdminEmailModal({ employeeId, employeeName, currentEmail, onClose, onChanged }: Props) {
  const { showToast } = useToast();
  const [newEmail, setNewEmail]   = useState("");
  const [error, setError]         = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving]       = useState(false);

  function handleContinue() {
    setError(null);
    const trimmed = newEmail.trim();
    if (!trimmed) { setError("Enter the new login email."); return; }
    if (!EMAIL_RE.test(trimmed)) { setError("Enter a valid email address."); return; }
    if (trimmed.toLowerCase() === currentEmail.toLowerCase()) {
      setError("That is already the current login email.");
      return;
    }
    setConfirming(true);
  }

  async function confirmChange() {
    setSaving(true);
    setError(null);
    try {
      const res = await clientApi.post<{ message: string; data?: { email: string; new_email_sent?: boolean; old_email_sent?: boolean } }>(
        API.employees.changeEmail(employeeId),
        { new_email: newEmail.trim() },
      );
      const data = res.data.data;
      showToast(res.data.message, data && (data.new_email_sent === false || data.old_email_sent === false) ? "error" : "success");
      onChanged(data?.email ?? newEmail.trim());
      onClose();
    } catch (err: unknown) {
      const msg = (err as { message?: string }).message ?? "Failed to change login email.";
      setError(msg);
      setConfirming(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden">
        <div className="px-6 pt-6 pb-4 text-center">
          <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
            <i className="ti ti-mail-cog text-xl text-amber-600" />
          </div>
          <p className="text-sm font-bold text-gray-800 mb-1">
            {confirming ? "Confirm Email Change?" : "Change Login Email"}
          </p>
          {!confirming && (
            <p className="text-sm text-gray-500">
              Update the login email for <strong className="text-gray-700">{employeeName}</strong>{"'"}s System Admin account. Their password will not change.
            </p>
          )}
        </div>

        <div className="px-6 pb-2">
          {error && (
            <div className="mb-3 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-xs">{error}</div>
          )}

          {confirming ? (
            <div className="text-sm text-gray-600 mb-2">
              <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50 mb-2">
                <span className="text-xs text-gray-500">Current Email</span>
                <span className="font-medium text-gray-700">{currentEmail}</span>
              </div>
              <div className="flex items-center justify-center text-gray-400 mb-2">
                <i className="ti ti-arrow-down" />
              </div>
              <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50 mb-3">
                <span className="text-xs text-gray-500">New Email</span>
                <span className="font-semibold text-amber-700">{newEmail.trim()}</span>
              </div>
              <p className="text-xs text-gray-500">
                They will need to log in with the new email going forward. A confirmation will be sent to the new
                address, and a security notice to the old one.
              </p>
            </div>
          ) : (
            <div className="mb-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">New Login Email</label>
              <input
                type="email"
                autoFocus
                value={newEmail}
                onChange={e => { setNewEmail(e.target.value); setError(null); }}
                placeholder="new.email@company.com"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          )}
        </div>

        <div className="flex gap-2 px-6 pb-5 pt-2">
          <button
            onClick={confirming ? () => setConfirming(false) : onClose}
            disabled={saving}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          >
            {confirming ? "Back" : "Cancel"}
          </button>
          <button
            onClick={confirming ? confirmChange : handleContinue}
            disabled={saving}
            className="flex-1 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {saving ? <><i className="ti ti-loader-2 animate-spin" /> Changing…</> : confirming ? "Yes, Change Email" : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
