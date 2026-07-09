"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { Holiday } from "@/types/holidays";

const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(iso: string) {
  const [y, m, d] = iso.split("-");
  return `${parseInt(d)} ${MONTH_SHORT[parseInt(m) - 1]} ${y}`;
}

interface Props {
  holiday:   Holiday;
  onClose:   () => void;
  onDeleted: () => void;
}

export default function DeleteHolidayModal({ holiday, onClose, onDeleted }: Props) {
  const { showToast } = useToast();
  const [deleting, setDeleting] = useState(false);

  async function confirmDelete() {
    setDeleting(true);
    try {
      const res = await clientApi.delete<{ message: string }>(API.leave.holidayDetail(holiday.id));
      showToast(res.data.message, "success");
      onDeleted();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to delete holiday.";
      showToast(msg, "error");
      setDeleting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden">
        <div className="px-6 pt-6 pb-4 text-center">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
            <i className="ti ti-trash text-xl text-red-600" />
          </div>
          <p className="text-sm font-bold text-gray-800 mb-1">Delete Holiday?</p>
          <p className="text-sm text-gray-500">
            <strong className="text-gray-700">{holiday.name}</strong> ({fmtDate(holiday.date)}) will be permanently removed.
          </p>
        </div>
        <div className="flex gap-2 px-6 pb-5">
          <button onClick={onClose} disabled={deleting}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            Cancel
          </button>
          <button onClick={confirmDelete} disabled={deleting}
            className="flex-1 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2">
            {deleting ? <><i className="ti ti-loader-2 animate-spin" /> Deleting…</> : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
