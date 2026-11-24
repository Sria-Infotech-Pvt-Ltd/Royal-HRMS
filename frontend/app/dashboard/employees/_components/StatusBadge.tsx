import { tr } from "@/lib/i18n/tr";
import { STATUS_META, type EmployeeStatus } from "../_data";

/** Reusable status pill — used in the list table and the profile header. */
export default function StatusBadge({
  status,
  withDot = false,
}: {
  status: EmployeeStatus;
  withDot?: boolean;
}) {
  const meta = STATUS_META[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${meta.cls}`}
    >
      {withDot && <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />}
      {tr(meta.label)}
    </span>
  );
}
