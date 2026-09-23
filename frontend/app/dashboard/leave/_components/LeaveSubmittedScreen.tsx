import { LeaveRequest, LEAVE_TYPE_CONFIG, fmtDate } from "../_data";
import { type LeaveForm } from "./applyLeaveFormHelpers";

interface LeaveSubmittedScreenProps {
  submitted: LeaveRequest;
  leaveType: LeaveForm["leave_type"];
  onApplyAnother: () => void;
  onCancel: () => void;
}

export default function LeaveSubmittedScreen({ submitted, leaveType, onApplyAnother, onCancel }: LeaveSubmittedScreenProps) {
  const ltConfig = LEAVE_TYPE_CONFIG[leaveType];
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="bg-[var(--surface)] rounded-3xl border border-[var(--outline-v)] shadow-lg p-10 text-center w-full max-w-md">
        <div className="w-20 h-20 rounded-full bg-[var(--success-c)] flex items-center justify-center mx-auto mb-6">
          <i className="ti ti-circle-check text-4xl text-[var(--success)]" />
        </div>
        <h2 className="text-xl font-bold text-[var(--on-bg)] mb-2">Request Submitted!</h2>
        <p className="text-sm text-[var(--on-variant)] mb-1">
          Your <strong className="text-[var(--primary)]">{ltConfig.label}</strong> request for{" "}
          <strong className="text-[var(--primary)]">{submitted.total_days} day{submitted.total_days !== 1 ? "s" : ""}</strong> has been sent for approval.
        </p>
        <p className="text-xs text-[var(--on-variant)] mb-8">{fmtDate(submitted.start_date)} → {fmtDate(submitted.end_date)}</p>
        <div className="flex gap-3 justify-center">
          <button onClick={onApplyAnother}
            className="px-5 py-2.5 rounded-xl border border-[var(--outline-v)] text-sm font-medium text-[var(--on-variant)] hover:bg-[var(--bg-low)]">
            Apply Another
          </button>
          <button onClick={onCancel}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold text-[var(--on-primary)]"
            style={{ background: "var(--primary)" }}>
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
