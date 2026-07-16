"use client";

import { useState } from "react";

interface Props {
  employee: string;
  leaveType: string;
  onCancel:  () => void;
  onConfirm: (reason: string) => void;
}

export default function RejectModal({ employee, leaveType, onCancel, onConfirm }: Props) {
  const [reason, setReason] = useState("");
  const [error,  setError]  = useState("");

  function submit() {
    if (!reason.trim()) { setError("Rejection reason is required."); return; }
    onConfirm(reason.trim());
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal card */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md z-10 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
              <i className="ti ti-circle-x text-red-500 text-lg" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#1a2b4a]">Reject Leave Request</h3>
              <p className="text-xs text-gray-400 mt-0.5">{employee} · {leaveType}</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <i className="ti ti-x text-sm" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-semibold text-[#1a2b4a]">
              Rejection Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={e => { setReason(e.target.value); if (e.target.value.trim()) setError(""); }}
              placeholder="Explain why this leave request is being rejected…"
              rows={4}
              maxLength={300}
              autoFocus
              className={[
                "w-full rounded-xl border px-3.5 py-3 text-sm text-gray-700 bg-white resize-none",
                "focus:outline-none focus:ring-2 focus:ring-red-200 focus:border-red-400 transition",
                error ? "border-red-400 bg-red-50" : "border-gray-200",
              ].join(" ")}
            />
            <div className="flex justify-between items-center">
              {error
                ? <p className="text-xs text-red-500 flex items-center gap-1"><i className="ti ti-alert-circle" />{error}</p>
                : <span />}
              <span className="text-xs text-gray-400 ml-auto">{reason.length}/300</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 pb-6">
          <button
            onClick={onCancel}
            className="px-5 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors"
          >
            <i className="ti ti-circle-x" /> Submit Rejection
          </button>
        </div>
      </div>
    </div>
  );
}
