"use client";

import { useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface LeaveType {
  id:          number;
  name:        string;
  code:        string;
  color:       string;
  max_days:    number;
  is_paid:     boolean;
  carry_fwd:   boolean;
  doc_needed:  boolean;
  gender:      string;
  is_active:   boolean;
  description: string;
}

// ─── Seed data ────────────────────────────────────────────────────────────────

const SEED: LeaveType[] = [
  { id: 1, name: "Casual Leave",      code: "CL",  color: "#1e4e8c", max_days: 12, is_paid: true,  carry_fwd: false, doc_needed: false, gender: "All",    is_active: true,  description: "For personal errands and short breaks." },
  { id: 2, name: "Earned Leave",      code: "EL",  color: "#1b8a6b", max_days: 18, is_paid: true,  carry_fwd: true,  doc_needed: false, gender: "All",    is_active: true,  description: "Accrues monthly. Carry-forward allowed up to 15 days." },
  { id: 3, name: "Sick Leave",        code: "SL",  color: "#b5651d", max_days: 6,  is_paid: true,  carry_fwd: false, doc_needed: true,  gender: "All",    is_active: true,  description: "Medical certificate required for leaves exceeding 2 days." },
  { id: 4, name: "Maternity Leave",   code: "ML",  color: "#ad95cf", max_days: 84, is_paid: true,  carry_fwd: false, doc_needed: true,  gender: "Female", is_active: true,  description: "84 working days as per the Maternity Benefit Act." },
  { id: 5, name: "Leave Without Pay", code: "LWP", color: "#6b7280", max_days: 30, is_paid: false, carry_fwd: false, doc_needed: false, gender: "All",    is_active: true,  description: "Unpaid leave when all paid leaves are exhausted." },
  { id: 6, name: "Paternity Leave",   code: "PL",  color: "#0e7c86", max_days: 15, is_paid: true,  carry_fwd: false, doc_needed: true,  gender: "Male",   is_active: false, description: "15 days for new fathers within 3 months of birth." },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function LeaveTypes() {
  const [types,         setTypes]         = useState<LeaveType[]>(SEED);
  const [deleteTarget,  setDeleteTarget]  = useState<LeaveType | null>(null);

  function confirmDelete() {
    if (!deleteTarget) return;
    setTypes(prev => prev.filter(t => t.id !== deleteTarget.id));
    setDeleteTarget(null);
  }

  if (types.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-400">
        <i className="ti ti-beach text-5xl text-gray-200" />
        <p className="text-sm font-medium text-gray-500">No leave types configured.</p>
        <p className="text-xs text-gray-400">Go to <strong className="text-gray-600">Settings → Leave Policy</strong> to add leave types.</p>
      </div>
    );
  }

  return (
    <>
      {/* Cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {types.map(t => (
          <div
            key={t.id}
            className={[
              "bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden",
              "relative flex flex-col transition-opacity",
              t.is_active ? "opacity-100" : "opacity-55",
            ].join(" ")}
          >
            {/* Left accent bar */}
            <div
              className="absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl"
              style={{ background: t.is_active ? t.color : "#d1d5db" }}
            />

            <div className="p-5 pl-6 flex flex-col gap-4 flex-1">
              {/* Header */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center font-extrabold text-sm flex-shrink-0"
                    style={{ background: `${t.color}20`, color: t.color }}
                  >
                    {t.code}
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 text-sm leading-tight">{t.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{t.gender} · {t.is_paid ? "Paid" : "Unpaid"}</p>
                  </div>
                </div>

                {/* Right: status badge + delete */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <span className={[
                    "px-2.5 py-0.5 rounded-full text-xs font-semibold",
                    t.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500",
                  ].join(" ")}>
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    onClick={() => setDeleteTarget(t)}
                    title={`Delete ${t.name}`}
                    className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-400 hover:border-red-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                  >
                    <i className="ti ti-trash text-xs" />
                  </button>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-gray-500 leading-relaxed">{t.description}</p>

              {/* Attribute chips */}
              <div className="flex flex-wrap gap-2 mt-auto">
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 text-gray-600 text-xs">
                  <i className="ti ti-calendar text-xs" /> {t.max_days}d / year
                </span>
                {t.carry_fwd && (
                  <span
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs"
                    style={{ background: `${t.color}15`, color: t.color }}
                  >
                    <i className="ti ti-repeat text-xs" /> Carry fwd
                  </span>
                )}
                {t.doc_needed && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-50 text-amber-600 text-xs">
                    <i className="ti ti-file-certificate text-xs" /> Doc required
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Delete confirmation modal ──────────────────────────────────────── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden">
            <div className="px-6 pt-6 pb-4 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                <i className="ti ti-trash text-xl text-red-600" />
              </div>
              <p className="text-sm font-bold text-gray-800 mb-2">Delete Leave Type?</p>
              <p className="text-sm text-gray-500">
                <strong
                  className="font-semibold"
                  style={{ color: deleteTarget.color }}
                >
                  {deleteTarget.name}
                </strong>{" "}
                will be permanently removed. Employees with existing{" "}
                <strong className="text-gray-700">{deleteTarget.code}</strong> balances may be affected.
              </p>
            </div>
            <div className="flex gap-2 px-6 pb-5">
              <button
                onClick={() => setDeleteTarget(null)}
                className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
