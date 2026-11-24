"use client";

// The workflows, one row each: its icon and name, how many levels it has, and the approval flow drawn out. Edit opens the editor inside
// that row, under the flow.

import { useT } from "@/hooks/useI18n";
import type { EditState } from "@/hooks/useApprovalRules";
import type { GlobalApprovalRule } from "@/types/approvalMatrix";
import ApprovalFlow from "./ApprovalFlow";
import ApprovalRuleEditor from "./ApprovalRuleEditor";
import { BRAND, WORKFLOW_BLURBS, WORKFLOW_ICONS, flowOfRule, tint } from "./approvalFlowView";

const SHIMMER = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" } as const;

interface EditorProps { applyAll: boolean; saving: boolean; apiError: string; onApplyAll: (value: boolean) => void; onChoice: (level: "l1_choice" | "l2_choice", value: string) => void; onSave: () => void }
interface Props extends EditorProps { rules: GlobalApprovalRule[]; loading: boolean; editing: EditState | null; onEdit: (rule: GlobalApprovalRule) => void; onClose: () => void }

export default function ApprovalRulesList({ rules, loading, editing, onEdit, onClose, ...editorProps }: Props) {
  const t = useT();
  return (
    <section aria-label={t("Approval workflows")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "14px 20px", borderBottom: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 8, fontSize: 15, fontWeight: 800, color: "var(--on-bg)" }}>
        <i className="ti ti-route" aria-hidden="true" style={{ color: BRAND }} /> {t("Workflows")}
      </header>

      {loading && [0, 1, 2].map(row => <div key={row} aria-label={t("Loading")} style={{ ...SHIMMER, height: 74, margin: 16, borderRadius: 12 }} />)}

      {!loading && rules.length === 0 && (
        <div style={{ padding: "40px 16px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-route-off" aria-hidden="true" style={{ fontSize: 36, color: "var(--outline)" }} />
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 6 }}>{t("No approval workflows found.")}</div>
        </div>
      )}

      {!loading && rules.map(rule => {
        const twoLevel = Boolean(rule.l2_approver_kind);
        const isOpen = editing?.workflow_type === rule.workflow_type;
        return (
          <div key={rule.workflow_type} style={{ borderBottom: "1px solid var(--outline-v)" }}>
            <div className="ar-row" style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap", padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flex: "0 0 240px", minWidth: 200 }}>
                <span aria-hidden="true" style={{ width: 42, height: 42, borderRadius: 12, display: "grid", placeItems: "center", fontSize: 21, background: tint(BRAND, 0.12), color: BRAND }}><i className={`ti ${WORKFLOW_ICONS[rule.workflow_type] ?? "ti-check"}`} /></span>
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 800, color: "var(--on-bg)" }}>{rule.workflow_label}</div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{t(WORKFLOW_BLURBS[rule.workflow_type] ?? "Approval workflow")}</div>
                  <span style={{ display: "inline-block", marginTop: 4, fontSize: 11, fontWeight: 700, padding: "1px 9px", borderRadius: 999, background: tint(BRAND, 0.12), color: BRAND }}>{twoLevel ? t("2 levels") : t("1 level")}</span>
                </div>
              </div>
              <div style={{ flex: "1 1 420px", minWidth: 0 }}><ApprovalFlow steps={flowOfRule(rule)} compact /></div>
              <button className="btn btn-ghost" aria-label={t("Edit {label}", { label: rule.workflow_label })} aria-expanded={isOpen} onClick={() => isOpen ? onClose() : onEdit(rule)} style={{ padding: "6px 14px", fontSize: 12.5 }}>
                <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-edit"}`} /> {isOpen ? t("Close") : t("Edit")}
              </button>
            </div>
            {isOpen && editing && <ApprovalRuleEditor editing={editing} workflowCount={rules.length} onClose={onClose} {...editorProps} />}
          </div>
        );
      })}
    </section>
  );
}
