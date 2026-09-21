"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";

interface Props {
  employeeId:   string;   // employee_id code, e.g. "EMP00003" — matches API.employees.detail
  employeeName: string;
  onClose:      () => void;
}

export default function ResetPasswordModal({ employeeId, employeeName, onClose }: Props) {
  const { showToast } = useToast();
  const [resetting, setResetting] = useState(false);

  async function confirmReset() {
    setResetting(true);
    try {
      const res = await clientApi.post<{ message: string; data?: { email_sent?: boolean } }>(
        API.employees.resetPassword(employeeId)
      );
      // The reset itself always succeeds here (2xx) — data.email_sent tells us
      // whether the new-credentials email actually went out, so a delivery
      // failure is still surfaced clearly even though the password did change.
      showToast(res.data.message, res.data.data?.email_sent === false ? "error" : "success");
      onClose();
    } catch (err: unknown) {
      const msg = (err as { message?: string }).message ?? "Failed to reset password.";
      showToast(msg, "error");
      setResetting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden">
        <div className="px-6 pt-6 pb-4 text-center">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
            <i className="ti ti-key text-xl text-red-600" />
          </div>
          <p className="text-sm font-bold text-gray-800 mb-1">Reset Password?</p>
          <p className="text-sm text-gray-500">
            A new temporary password will be generated for <strong className="text-gray-700">{employeeName}</strong> and
            emailed to them. Their current password will stop working immediately.
          </p>
        </div>
        <div className="flex gap-2 px-6 pb-5">
          <button onClick={onClose} disabled={resetting}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            Cancel
          </button>
          <button onClick={confirmReset} disabled={resetting}
            className="flex-1 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2">
            {resetting ? <><i className="ti ti-loader-2 animate-spin" /> Resetting…</> : "Reset Password"}
          </button>
        </div>
      </div>
    </div>
  );
}
