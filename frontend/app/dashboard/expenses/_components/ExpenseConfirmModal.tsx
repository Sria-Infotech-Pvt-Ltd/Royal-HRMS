"use client";

interface Expense {
  id:     number;
  title:  string;
  amount: number;
}

interface ExpenseConfirmModalProps {
  type:      "approve" | "reject";
  expense:   Expense;
  onConfirm: () => void;
  onCancel:  () => void;
}

export default function ExpenseConfirmModal({
  type, expense, onConfirm, onCancel,
}: ExpenseConfirmModalProps) {
  const isApprove = type === "approve";

  const title  = isApprove ? "Approve Expense" : "Reject Expense";
  const icon   = isApprove ? "ti-check"   : "ti-x";
  const color  = isApprove ? "var(--success)" : "var(--error)";
  const btnCls = isApprove ? "btn-success" : "btn-danger";

  const body = isApprove
    ? "This expense will be approved and queued for reimbursement in the next payroll cycle. Continue?"
    : "This expense will be rejected. The employee will be notified. Continue?";

  return (
    <div
      className="modal-overlay open"
      style={{ zIndex: 1010 }}
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="modal" style={{ maxWidth: "min(420px, 94vw)" }}>
        <div className="modal-header">
          <div className="modal-title" style={{ color }}>
            <i className={`ti ${icon}`} style={{ marginRight: 8 }} />
            {title}
          </div>
          <button className="modal-close" onClick={onCancel} suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: 12 }}>
            {body}
          </p>
          <div style={{
            background: "var(--bg-low)",
            border: "1px solid var(--outline-v)",
            borderRadius: "var(--radius)",
            padding: "10px 14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>
              {expense.title}
            </span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
              ₹{expense.amount.toLocaleString("en-IN")}
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel} suppressHydrationWarning>
            Cancel
          </button>
          <button
            className={`btn ${btnCls}`}
            onClick={onConfirm}
            suppressHydrationWarning
          >
            <i className={`ti ${icon}`} />
            {isApprove ? "Yes, Approve" : "Yes, Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
