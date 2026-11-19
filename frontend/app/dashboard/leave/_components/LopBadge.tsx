import type { LeaveRequest } from "../_data";
import { tr } from "@/lib/i18n/tr";

interface Props {
  request: LeaveRequest;
}

export default function LopBadge({ request }: Props) {
  if (request.lop_days <= 0) return null;
  return (
    <span
      className="badge badge-warn"
      style={{ marginLeft: 6 }}
      title={tr(request.lop_days === 1 ? "{count} day of this request is Leave Without Pay" : "{count} days of this request are Leave Without Pay", { count: request.lop_days })}
    >
      {tr("LOP")} {request.lop_days}d
    </span>
  );
}
