"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate as sharedFormatDate } from "@/lib/formatDate";
import type { PaginatedResponse } from "@/types/attendance";
import ExpenseFormModal from "./ExpenseFormModal";
import ExpenseDetailModal from "./ExpenseDetailModal";
import ExpenseStatsRow, { type ExpenseStatsData } from "./ExpenseStatsRow";
import ExpenseRecentList from "./ExpenseRecentList";
import { EXPENSE_COLOUR, tint } from "./expenseView";

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

type ExpenseStats = ExpenseStatsData;

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

export function formatDate(iso: string): string {
  return sharedFormatDate(iso);
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

  function handleSaved() {
    setShowNewExpense(false);
    refetch();
    refetchStats();
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14, padding: "20px 24px", marginBottom: 18, borderRadius: 18, border: `1px solid ${tint(EXPENSE_COLOUR.brand, 0.2)}`, background: `linear-gradient(135deg, ${tint(EXPENSE_COLOUR.brand, 0.12)} 0%, var(--surface) 65%)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span aria-hidden="true" style={{ width: 50, height: 50, borderRadius: 15, display: "grid", placeItems: "center", fontSize: 26, color: "#fff", background: EXPENSE_COLOUR.brand, boxShadow: `0 6px 16px ${tint(EXPENSE_COLOUR.brand, 0.35)}` }}><i className="ti ti-receipt-2" /></span>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: "var(--on-bg)" }}>Expenses</h1>
            <p style={{ margin: "2px 0 0", fontSize: 13.5, color: "var(--on-variant)" }}>Submit and track your reimbursement claims</p>
          </div>
        </div>
      </div>

      <ExpenseStatsRow stats={stats ?? null} loading={!stats && !error} />

      {error && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      {/* Latest claims only; the full history lives in My Requests */}
      <ExpenseRecentList
        claims={expenseList} loading={loading} categoryLabel={CATEGORY_LABEL} formatDate={formatDate}
        onOpen={setSelectedExpense} onNew={() => setShowNewExpense(true)} limit={RECENT_COUNT}
      />

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
