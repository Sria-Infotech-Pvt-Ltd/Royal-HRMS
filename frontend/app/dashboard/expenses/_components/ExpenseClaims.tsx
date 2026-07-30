"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PaginatedResponse } from "@/types/attendance";
import ExpenseFormModal from "./ExpenseFormModal";
import ExpenseDetailModal from "./ExpenseDetailModal";

// ─── Types ────────────────────────────────────────────────────────────────────

type ExpenseCategory = "travel" | "meals" | "equipment" | "other";
type ExpenseStatus   = "pending" | "approved" | "rejected";
type FilterTab       = "all" | ExpenseCategory;

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

const FILTER_TABS: { value: FilterTab; label: string; icon: string }[] = [
  { value: "all",       label: "All Claims", icon: "ti-list"                   },
  { value: "travel",    label: "Travel",     icon: "ti-plane-departure"        },
  { value: "meals",     label: "Meals",      icon: "ti-tools-kitchen-2"        },
  { value: "equipment", label: "Equipment",  icon: "ti-device-desktop"         },
  { value: "other",     label: "Other",      icon: "ti-dots-circle-horizontal" },
];

export const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  travel:    "Travel",
  meals:     "Meals",
  equipment: "Equipment",
  other:     "Other",
};

const CATEGORY_ICON: Record<ExpenseCategory, string> = {
  travel:    "ti-plane-departure",
  meals:     "ti-tools-kitchen-2",
  equipment: "ti-device-desktop",
  other:     "ti-dots-circle-horizontal",
};

const CATEGORY_STYLE: Record<ExpenseCategory, { bg: string; color: string }> = {
  travel:    { bg: "rgba(30,78,140,0.10)",   color: "var(--primary)"    },
  meals:     { bg: "rgba(181,101,29,0.10)",  color: "var(--warn)"       },
  equipment: { bg: "rgba(14,124,134,0.10)",  color: "var(--info)"       },
  other:     { bg: "var(--bg-high)",         color: "var(--on-variant)" },
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

export default function ExpenseClaims() {
  const [activeFilter,    setActiveFilter]    = useState<FilterTab>("all");
  const [showNewExpense,  setShowNewExpense]  = useState(false);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);

  const listUrl = useMemo(() => {
    if (activeFilter === "all") return API.expenses.list;
    return `${API.expenses.list}?category=${activeFilter}`;
  }, [activeFilter]);

  // /expenses/ returns a paginated envelope ({ results, count, ... }), not a
  // bare array — fetching it as Expense[] made Array.isArray() always false,
  // which silently rendered the empty state no matter how many claims existed.
  const { data: expensesPage, loading, error, refetch } = useFetch<PaginatedResponse<Expense>>(listUrl);
  const { data: stats,        refetch: refetchStats }   = useFetch<ExpenseStats>(API.expenses.stats);

  const expenseList = expensesPage?.results ?? [];

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
          <div className="page-title">Expense Claims</div>
          <div className="page-sub">Submit and track your reimbursement requests</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowNewExpense(true)}>
            <i className="ti ti-plus" /> New Expense
          </button>
        </div>
      </div>

      {/* Stats */}
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
          <div className="stat-icon si-info"><i className="ti ti-cash" /></div>
          <div className="stat-label">Total Amount</div>
          <div className="stat-value">{formatAmount(totalAmount)}</div>
        </div>
      </div>

      {/* Category filter tabs */}
      <div className="filter-bar filter-scroll mb-16">
        {FILTER_TABS.map(tab => (
          <button
            key={tab.value}
            className={`btn ${activeFilter === tab.value ? "btn-filled" : "btn-ghost"}`}
            onClick={() => setActiveFilter(tab.value)}
          >
            <i className={`ti ${tab.icon}`} /> {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      {/* Expense list */}
      <div className="card">
        {loading ? (
          <div className="text-center py-10">
            <i className="ti ti-loader-2 spin text-3xl" />
          </div>
        ) : expenseList.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-wallet" />
            <h3>No expense claims yet</h3>
            <p>Submit a new expense to get started. Attach your receipt for faster approval.</p>
          </div>
        ) : (
          expenseList.map((expense, idx) => {
            const catStyle     = CATEGORY_STYLE[expense.category] ?? CATEGORY_STYLE.other;
            const catIcon      = CATEGORY_ICON[expense.category]  ?? "ti-dots-circle-horizontal";
            const catLabel     = CATEGORY_LABEL[expense.category] ?? expense.category;
            const { cls, label } = STATUS_BADGE[expense.status]   ?? STATUS_BADGE.pending;
            const receiptCount = expense.receipts?.length ?? 0;

            return (
              <div
                key={expense.expense_number}
                onClick={() => setSelectedExpense(expense)}
                className={`flex items-center gap-3.5 px-5 py-4 flex-wrap cursor-pointer hover:bg-[var(--bg-low)] transition-colors ${idx < expenseList.length - 1 ? "border-b border-[var(--outline-v)]" : ""}`}
              >
                {/* Category icon */}
                <div
                  className="w-11 h-11 rounded-[10px] flex items-center justify-center text-xl flex-shrink-0"
                  style={{ background: catStyle.bg, color: catStyle.color }}
                >
                  <i className={`ti ${catIcon}`} />
                </div>

                {/* Details */}
                <div className="flex-1 min-w-[160px]">
                  <div className="font-semibold text-sm text-[var(--on-bg)] mb-1">
                    {expense.title}
                  </div>
                  <div className="flex items-center gap-2.5 flex-wrap text-xs text-[var(--on-variant)]">
                    <span className="text-[var(--outline)]">{expense.expense_ref}</span>
                    {expense.employee_name && (
                      <span className="flex items-center gap-1">
                        <i className="ti ti-user text-[13px]" /> {expense.employee_name}
                      </span>
                    )}
                    {expense.branch_name && (
                      <span className="flex items-center gap-1">
                        <i className="ti ti-building text-[13px]" /> {expense.branch_name}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <i className="ti ti-calendar text-[13px]" /> {formatDate(expense.expense_date)}
                    </span>
                    {receiptCount > 0 && (
                      <span className="flex items-center gap-1">
                        <i className="ti ti-paperclip text-[13px]" /> {receiptCount} receipt{receiptCount !== 1 ? "s" : ""}
                      </span>
                    )}
                    <span className="badge badge-neutral text-[10px]">
                      {catLabel}
                    </span>
                  </div>
                </div>

                {/* Amount + status */}
                <div className="flex items-center gap-2.5 flex-shrink-0">
                  <span className="text-base font-bold text-[var(--on-bg)]">
                    ₹{parseFloat(String(expense.amount)).toLocaleString("en-IN")}
                  </span>
                  <span className={`badge ${cls}`}>{label}</span>
                </div>
              </div>
            );
          })
        )}
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
