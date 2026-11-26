"use client";

// Shown after "Move employees" is confirmed: who moved and to which position, and who was skipped with the server's reason.

import { useT } from "@/hooks/useI18n";
import type { BulkMoveResult } from "@/hooks/useBulkMoveOrgUnit";

interface MoveResultViewProps { result: BulkMoveResult; nameOf: (code: string) => string }

export default function MoveResultView({ result, nameOf }: MoveResultViewProps) {
  const t = useT();
  const isAllDone = result.skipped.length === 0;

  return (
    <div className="mstep on" style={{ padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: isAllDone ? "var(--ok-bg)" : "var(--warn-bg)", color: isAllDone ? "var(--ok)" : "var(--warn)", fontSize: 24 }}>
          <i className={`ti ${isAllDone ? "ti-circle-check" : "ti-alert-triangle"}`} />
        </span>
        <div>
          <h3 style={{ fontSize: 20, fontWeight: 800 }}>{t("{count} employee(s) moved.", { count: result.moved.length })}</h3>
          <p className="hint" style={{ fontSize: 12.5 }}>
            {isAllDone ? t("Everyone you chose has moved.") : t("{count} could not be moved; see the reasons below.", { count: result.skipped.length })}
          </p>
        </div>
      </div>

      {result.moved.length > 0 && (
        <div style={{ border: "1px solid var(--line-soft)", borderRadius: 13, overflow: "hidden" }}>
          {result.moved.map(row => (
            <div key={row.employee_id} className="flex items-center" style={{ gap: 10, padding: "9px 14px", borderBottom: "1px solid var(--line-soft)", fontSize: 12.5 }}>
              <i className="ti ti-check" style={{ color: "var(--ok)" }} />
              <span style={{ flex: 1, minWidth: 0 }}><b style={{ fontWeight: 600 }}>{nameOf(row.employee_id)}</b> <span style={{ color: "var(--faint)" }}>{row.employee_id}</span></span>
              <span style={{ color: "var(--muted)" }}>{row.position} · {row.org_unit}</span>
            </div>
          ))}
        </div>
      )}

      {result.skipped.length > 0 && (
        <div className="note warn">
          <b>{t("Not moved")}</b>
          {result.skipped.map(row => (
            <span key={row.employee_id} style={{ display: "block" }}>{nameOf(row.employee_id)} ({row.employee_id}): {row.reason}</span>
          ))}
        </div>
      )}
    </div>
  );
}
