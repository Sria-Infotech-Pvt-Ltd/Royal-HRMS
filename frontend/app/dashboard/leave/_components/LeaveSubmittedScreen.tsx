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
  const dayCount = `${submitted.total_days} day${submitted.total_days !== 1 ? "s" : ""}`;
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--success-c)]">
        <i className="ti ti-check text-2xl text-[var(--success)]" />
      </div>
      <h2 className="mb-1 text-lg font-semibold text-[var(--on-bg)]">Request submitted</h2>
      <p className="max-w-sm text-[13px] text-[var(--on-variant)]">
        Your {ltConfig.label.toLowerCase()} request for {dayCount} ({fmtDate(submitted.start_date)}
        {submitted.end_date !== submitted.start_date && ` – ${fmtDate(submitted.end_date)}`}) has been sent for approval.
      </p>
      <div className="mt-6 flex gap-2.5">
        <button type="button" className="btn btn-ghost" onClick={onApplyAnother}>Request another</button>
        <button type="button" className="btn btn-filled" onClick={onCancel}>Done</button>
      </div>
    </div>
  );
}
