import type { LeaveRequest } from "../_data";

interface Props {
  request: LeaveRequest;
}

export default function LopBadge({ request }: Props) {
  if (request.lop_days <= 0) return null;
  return (
    <span
      className="badge badge-warn"
      style={{ marginLeft: 6 }}
      title={`${request.lop_days} day${request.lop_days !== 1 ? "s" : ""} of this request is Leave Without Pay`}
    >
      LOP {request.lop_days}d
    </span>
  );
}
