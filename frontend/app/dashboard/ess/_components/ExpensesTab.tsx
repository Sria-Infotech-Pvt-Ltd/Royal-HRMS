"use client";

// ESS "Expenses" tab — a lighter, self-service-styled wrapper around the
// existing expense-claim flow. Listing reuses the shared `useFetch` hook
// against the same `API.expenses.list` endpoint (and the `Expense` type /
// category-label / status-badge maps) that the full Expenses page
// (`app/dashboard/expenses/_components/ExpenseClaims.tsx`) already defines,
// so nothing about fetching or labelling is duplicated. Creating a claim
// reuses `ExpenseFormModal` as-is rather than rebuilding its form/upload
// logic here.
//
// "View expense policy" looks for a real Document Center policy whose title
// mentions "expense" (category=policy, same endpoint PoliciesAssetsTab
// already reads) and links straight to it; if none has been uploaded yet it
// falls back to a plain link into the shared Document Center
// (/dashboard/documents) rather than the ESS "Documents" tab — that tab is
// now MyDocumentsTab, a personal document-verification screen with no
// "policy" category, so it can no longer stand in for browsing policies.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import type { PaginatedResponse } from "@/types/attendance";
import { DOCUMENTS_BASE, type ApiDocument } from "../../documents/_data";
import ExpenseFormModal from "../../expenses/_components/ExpenseFormModal";
import ExpenseDetailModal from "../../expenses/_components/ExpenseDetailModal";
import { CATEGORY_LABEL, STATUS_BADGE, type Expense } from "../../expenses/_components/ExpenseClaims";

const RECENT_COUNT = 5;

interface ProcessStep {
  title: string;
  description: string;
}

const PROCESS_STEPS: ProcessStep[] = [
  { title: "Submit expense and receipt reference", description: "Employee provides category, date, amount and business purpose." },
  { title: "Manager and payroll review",            description: "Policy limits and evidence are checked." },
  { title: "Payment after approval",                description: "Approved claims are scheduled for payroll or reimbursement." },
];

function formatAmount(amount: number | string): string {
  const value = typeof amount === "string" ? parseFloat(amount) : amount;
  return `₹${value.toLocaleString("en-IN")}`;
}

export default function ExpensesTab() {
  const [showNewExpense, setShowNewExpense] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);

  const { data: expensesPage, loading, error, refetch } =
    useFetch<PaginatedResponse<Expense>>(API.expenses.list);
  const { data: policyPage } =
    useFetch<PaginatedResponse<ApiDocument>>(`${DOCUMENTS_BASE}?category=policy&page_size=50`);

  const claims = (expensesPage?.results ?? []).slice(0, RECENT_COUNT);
  const allClaims = expensesPage?.results ?? [];
  const expensePolicyDoc = (policyPage?.results ?? []).find(d => d.title.toLowerCase().includes("expense"));

  // Step progress: step 1 (submission) is always reached — every claim in
  // this list is proof of that. Steps 2/3 light up once at least one real
  // claim has actually moved past "pending" / reached "approved". There is
  // no distinct "paid" status on Expense (only pending/approved/rejected —
  // payout is tracked separately via disbursed_in_payslip on the backend),
  // so "approved" is treated as having reached the payment stage.
  const hasReviewed = allClaims.some(c => c.status !== "pending");
  const hasApproved = allClaims.some(c => c.status === "approved");
  const stepDone = [true, hasReviewed, hasApproved];

  function handleSaved() {
    setShowNewExpense(false);
    refetch();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Expenses & claims</div>
          <div className="page-sub">Submit work expenses and follow approval or payment progress.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowNewExpense(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> New expense claim
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div className="form-row cols-2" style={{ alignItems: "flex-start" }}>
        {/* My claims */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-receipt" /> My claims</div>
          </div>
          <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
            Receipts, purpose and amount are required before submission.
          </p>
          <div className="table-wrap">
            {loading ? (
              <div className="text-center py-10">
                <i className="ti ti-loader-2 spin text-3xl" />
              </div>
            ) : claims.length === 0 ? (
              <div className="empty-state">
                <i className="ti ti-wallet" />
                <h3>No claims submitted</h3>
                <p>Your new claim will appear here and in My Requests.</p>
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Date</th>
                    <th>Amount</th>
                    <th style={{ textAlign: "center" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map(claim => {
                    const catLabel = CATEGORY_LABEL[claim.category] ?? claim.category;
                    const { cls, label } = STATUS_BADGE[claim.status] ?? STATUS_BADGE.pending;
                    return (
                      <tr key={claim.expense_number} onClick={() => setSelectedExpense(claim)} style={{ cursor: "pointer" }}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{catLabel}</div>
                          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{claim.title}</div>
                        </td>
                        <td>{formatDate(claim.expense_date)}</td>
                        <td style={{ fontWeight: 700 }}>{formatAmount(claim.amount)}</td>
                        <td style={{ textAlign: "center" }}><span className={`badge ${cls}`}>{label}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Claim process */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-list-check" /> Claim process</div>
          </div>
          <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
            {PROCESS_STEPS.map((step, index) => {
              const done = stepDone[index];
              return (
                <div key={step.title} style={{ display: "flex", gap: 12 }}>
                  <div style={{
                    flexShrink: 0, width: 12, height: 12, borderRadius: "50%", marginTop: 4,
                    background: done ? "var(--success)" : "transparent",
                    border: done ? "none" : "2px solid var(--outline-v)",
                  }} />
                  <div>
                    <div style={{ fontWeight: 500 }}>{step.title}</div>
                    <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{step.description}</div>
                  </div>
                </div>
              );
            })}
            {expensePolicyDoc ? (
              <a href={expensePolicyDoc.file_url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }}>
                <i className="ti ti-file-text" /> View expense policy
              </a>
            ) : (
              <a href="/dashboard/documents" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }}>
                <i className="ti ti-file-text" /> View expense policy
              </a>
            )}
          </div>
        </div>
      </div>

      {showNewExpense && (
        <ExpenseFormModal
          onClose={() => setShowNewExpense(false)}
          onSaved={handleSaved}
        />
      )}

      {selectedExpense && (
        <ExpenseDetailModal
          initialData={selectedExpense}
          onClose={() => setSelectedExpense(null)}
        />
      )}
    </div>
  );
}
