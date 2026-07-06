import { LeaveRequest, STATUS_BADGE, STATUS_LABEL } from "../_data";

interface Props {
  request: LeaveRequest;
}

export default function StatusCell({ request }: Props) {
  return <span className={STATUS_BADGE[request.status]}>{STATUS_LABEL[request.status]}</span>;
}
