"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PaginatedResponse } from "@/types/attendance";
import ExpenseFormModal from "./ExpenseFormModal";
import ExpenseDetailModal from "./ExpenseDetailModal";

// ─── Types ────────────────────────────────────────────────────────────────────

type ExpenseCategory = "travel" | "meals" | "equipment" | "other";
type ExpenseStatus   = "pending" | "approved" | "rejected";

export interface ExpenseReceipt {
  id:  string;
  url: string | null;
}

// The backend has no separate uuid `id` for an expense — expense_number (int)
// is the primary key used in the detail URL; expense_ref ("EXP002") is just
// its display form. See ExpenseSerializer / ExpenseDetailView on the backend.
export interface Expense {
  expense_number: number;
  expense_ref:    string;
  title:          string;
  category:       ExpenseCategory;
  amount:         number | string;
  expense_date:   string;
  description:    string;
  status:         ExpenseStatus;
  receipts:       ExpenseReceipt[];
  employee_name:  string;
  branch_name:    string;
  created_at:     string;
}

interface ExpenseStats {
  total:           number;
  pending:         number;
  approved:        number;
  rejected:        number;
  total_amount:    number;
  pending_amount:  number;
  approved_amount: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

export const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  travel:    "Travel",
  meals:     "Meals",
  equipment: "Equipment",
  other:     "Other",
};

export const STATUS_BADGE: Record<ExpenseStatus, { cls: string; label: string }> = {
  approved: { cls: "badge-success", label: "approved" },
  pending:  { cls: "badge-warn",    label: "pending"  },
  rejected: { cls: "badge-error",   label: "rejected" },
};

function formatAmount(amount: number | string): string {
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(1)}L`;
  if (n >= 1_000)   return `₹${(n / 1_000).toFixed(1)}K`;
  return `₹${n.toLocaleString("en-IN")}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
}

// ─── Component ────────────────────────────────────────────────────────────────

const RECENT_COUNT = 5;

interface Props {
  autoOpenNew?: boolean;
}

export default function ExpenseClaims({ autoOpenNew = false }: Props) {
  const [showNewExpense,  setShowNewExpense]  = useState(autoOpenNew);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);

  // /expenses/ returns a paginated envelope ({ results, count, ... }), not a
  // bare array — fetching it as Expense[] made Array.isArray() always false,
  // which silently rendered the empty state no matter how many claims existed.
  const { data: expensesPage, loading, error, refetch } = useFetch<PaginatedResponse<Expense>>(API.expenses.list);
  const { data: stats,        refetch: refetchStats }   = useFetch<ExpenseStats>(API.expenses.stats);

  const expenseList = expensesPage?.results ?? [];
  const recentClaims = expenseList.slice(0, RECENT_COUNT);

  function handleSaved() {
    setShowNewExpense(false);
    refetch();
    refetchStats();
  }

  const totalAmount = stats?.total_amount ?? 0;

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Expenses</div>
          <div className="page-sub">Submit and track your reimbursement claims</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowNewExpense(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> Submit Expense
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-file-invoice" /></div>
          <div className="stat-label">Total Claims</div>
          <div className="stat-value">{stats?.total ?? "—"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-clock" /></div>
          <div className="stat-label">Pending</div>
          <div className="stat-value">{stats?.pending ?? "—"}</div>
          {stats && stats.pending_amount > 0 && (
            <div className="stat-sub">₹{stats.pending_amount.toLocaleString("en-IN")}</div>
          )}
        </div>
        <div className="stat-card">
          <div className="stat-icon si-success"><i className="ti ti-check" /></div>
          <div className="stat-label">Approved</div>
          <div className="stat-value">{stats?.approved ?? "—"}</div>
          {stats && stats.approved_amount > 0 && (
            <div className="stat-sub">₹{stats.approved_amount.toLocaleString("en-IN")}</div>
          )}
        </div>
        <div className="stat-card">
          <div className="stat-icon si-error"><i className="ti ti-x" /></div>
          <div className="stat-label">Rejected</div>
          <div className="stat-value">{stats?.rejected ?? "—"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-info"><i className="ti ti-cash" /></div>
          <div className="stat-label">Total Claimed Amount</div>
          <div className="stat-value">{formatAmount(totalAmount)}</div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      {/* Recent Expense Claims — latest 5 only; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-receipt" /> Recent Expense Claims</div>
          <a href="/dashboard/my-requests?tab=expense" className="btn btn-ghost btn-sm">
            View All Expense Claims <i className="ti ti-arrow-right" />
          </a>
        </div>
        <div className="table-wrap">
          {loading ? (
            <div className="text-center py-10">
              <i className="ti ti-loader-2 spin text-3xl" />
            </div>
          ) : recentClaims.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-wallet" />
              <h3>No expense claims yet</h3>
              <p>Submit a new expense to get started. Attach your receipt for faster approval.</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Expense Type</th>
                  <th>Date</th>
                  <th>Amount</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentClaims.map(expense => {
                  const catLabel      = CATEGORY_LABEL[expense.category] ?? expense.category;
                  const { cls, label } = STATUS_BADGE[expense.status]    ?? STATUS_BADGE.pending;
                  return (
                    <tr key={expense.expense_number} onClick={() => setSelectedExpense(expense)} style={{ cursor: "pointer" }}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{catLabel}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{expense.title}</div>
                      </td>
                      <td>{formatDate(expense.expense_date)}</td>
                      <td style={{ fontWeight: 700 }}>₹{parseFloat(String(expense.amount)).toLocaleString("en-IN")}</td>
                      <td style={{ textAlign: "center" }}><span className={`badge ${cls}`}>{label}</span></td>
                      <td style={{ textAlign: "right" }} onClick={e => e.stopPropagation()}>
                        <button className="btn btn-ghost btn-sm" onClick={() => setSelectedExpense(expense)} suppressHydrationWarning>
                          <i className="ti ti-eye" /> View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* New Expense modal */}
      {showNewExpense && (
        <ExpenseFormModal
          onClose={() => setShowNewExpense(false)}
          onSaved={handleSaved}
        />
      )}

      {/* Expense detail modal */}
      {selectedExpense && (
        <ExpenseDetailModal
          initialData={selectedExpense}
          onClose={() => setSelectedExpense(null)}
        />
      )}
    </>
  );
}
