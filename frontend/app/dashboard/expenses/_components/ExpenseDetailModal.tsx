"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import {
  type Expense, CATEGORY_LABEL, STATUS_BADGE, formatDate,
} from "./ExpenseClaims";

interface Props {
  initialData: Expense;
  onClose:     () => void;
}

export default function ExpenseDetailModal({ initialData, onClose }: Props) {
  // Row data renders immediately; GET /expenses/<expense_number>/ then supplies
  // the current state in case status changed since the list loaded.
  const { data, loading, error } = useFetch<Expense>(
    API.expenses.detail(String(initialData.expense_number))
  );
  const expense = data ?? initialData;
  const { cls, label } = STATUS_BADGE[expense.status] ?? STATUS_BADGE.pending;

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ width: "min(520px, 95vw)", maxHeight: "90vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-receipt" style={{ marginRight: 8 }} />
            {expense.expense_ref}
          </div>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body flex flex-col gap-4">
          {loading && !data && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]">
              <i className="ti ti-loader-2 spin" /> Loading latest status…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--error)]">
              <i className="ti ti-alert-circle" /> Could not refresh — showing last known details.
            </div>
          )}

          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Title</p>
              <p className="text-sm font-medium text-[var(--on-bg)]">{expense.title}</p>
            </div>
            <span className={`badge ${cls} flex-shrink-0`}>{label}</span>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--outline-v)] pt-4">
            <div>
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Amount</p>
              <p className="text-base font-bold text-[var(--on-bg)]">
                ₹{parseFloat(String(expense.amount)).toLocaleString("en-IN")}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Category</p>
              <p className="text-sm text-[var(--on-bg)]">{CATEGORY_LABEL[expense.category] ?? expense.category}</p>
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--outline-v)] pt-4">
            <div>
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Employee</p>
              <p className="text-sm text-[var(--on-bg)]">{expense.employee_name || "—"}</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Branch</p>
              <p className="text-sm text-[var(--on-bg)]">{expense.branch_name || "—"}</p>
            </div>
          </div>

          <div className="border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Expense Date</p>
            <p className="text-sm text-[var(--on-bg)]">{formatDate(expense.expense_date)}</p>
          </div>

          {expense.description && (
            <div className="border-t border-[var(--outline-v)] pt-4">
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Description</p>
              <p className="text-sm text-[var(--on-bg)]">{expense.description}</p>
            </div>
          )}

          {expense.receipts.length > 0 && (
            <div className="border-t border-[var(--outline-v)] pt-4">
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-2">
                Receipts ({expense.receipts.length})
              </p>
              <div className="flex flex-col gap-1.5">
                {expense.receipts.map((receipt, idx) => (
                  receipt.url && (
                    <a
                      key={receipt.id}
                      href={receipt.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 text-sm text-[var(--primary)] hover:underline"
                    >
                      <i className="ti ti-paperclip" /> Receipt {idx + 1}
                    </a>
                  )
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
