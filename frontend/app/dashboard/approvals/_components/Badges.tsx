import { ApprovalKind, DisplayStatus, STATUS_CHIP, TYPE_BADGE } from "../_data";

export function TypeBadge({ kind }: { kind: ApprovalKind }) {
  const cfg = TYPE_BADGE[kind];
  return (
    <span className={`ta-type-badge ${cfg.cls}`}>
      <span className="dot" />
      {cfg.label}
    </span>
  );
}

export function StatusChip({ status }: { status: DisplayStatus }) {
  const cfg = STATUS_CHIP[status];
  return <span className={`ta-status-chip ${cfg.cls}`}>{cfg.label}</span>;
}
