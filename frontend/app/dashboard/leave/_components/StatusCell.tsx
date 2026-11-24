import { LeaveRequest, STATUS_BADGE, STATUS_LABEL } from "../_data";
import { tr } from "@/lib/i18n/tr";

interface Props {
  request: LeaveRequest;
}

export default function StatusCell({ request }: Props) {
  return <span className={STATUS_BADGE[request.status]}>{tr(STATUS_LABEL[request.status])}</span>;
}
