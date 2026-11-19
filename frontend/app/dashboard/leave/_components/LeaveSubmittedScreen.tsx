import { LeaveRequest, LEAVE_TYPE_CONFIG, fmtDate } from "../_data";
import { type LeaveForm } from "./applyLeaveFormHelpers";
import { tr } from "@/lib/i18n/tr";

interface LeaveSubmittedScreenProps {
  submitted: LeaveRequest;
  leaveType: LeaveForm["leave_type"];
  onApplyAnother: () => void;
  onCancel: () => void;
}

export default function LeaveSubmittedScreen({ submitted, leaveType, onApplyAnother, onCancel }: LeaveSubmittedScreenProps) {
  const ltConfig = LEAVE_TYPE_CONFIG[leaveType];
  const dayCount = tr(submitted.total_days === 1 ? "{count} day" : "{count} days", { count: submitted.total_days });
  const dateRange = submitted.end_date !== submitted.start_date ? `${fmtDate(submitted.start_date)} – ${fmtDate(submitted.end_date)}` : fmtDate(submitted.start_date);
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--success-c)]">
        <i className="ti ti-check text-2xl text-[var(--success)]" />
      </div>
      <h2 className="mb-1 text-lg font-semibold text-[var(--on-bg)]">{tr("Request submitted")}</h2>
      <p className="max-w-sm text-[13px] text-[var(--on-variant)]">
        {tr("Your {type} request for {days} ({dates}) has been sent for approval.", { type: ltConfig.label.toLowerCase(), days: dayCount, dates: dateRange })}
      </p>
      <div className="mt-6 flex gap-2.5">
        <button type="button" className="btn btn-ghost" onClick={onApplyAnother}>{tr("Request another")}</button>
        <button type="button" className="btn btn-filled" onClick={onCancel}>{tr("Done")}</button>
      </div>
    </div>
  );
}
