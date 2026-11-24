import { useT } from "@/hooks/useI18n";
import { ApprovalKind, DisplayStatus, STATUS_CHIP, TYPE_BADGE } from "../_data";

export function TypeBadge({ kind }: { kind: ApprovalKind }) {
  const t = useT();
  const cfg = TYPE_BADGE[kind];
  return (
    <span className={`ta-type-badge ${cfg.cls}`}>
      <span className="dot" />
      {t(cfg.label)}
    </span>
  );
}

export function StatusChip({ status }: { status: DisplayStatus }) {
  const t = useT();
  const cfg = STATUS_CHIP[status];
  return <span className={`ta-status-chip ${cfg.cls}`}>{t(cfg.label)}</span>;
}
