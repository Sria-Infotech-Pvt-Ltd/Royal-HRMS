"use client";

// The editor that opens inside a workflow's row (no pop-up). The flow at the top changes live as the two approvers are picked, so what is
// about to be saved is visible first. Level 1 is required; level 2 is optional. "Apply to all" sends the same approvers to every workflow.

import SearchableSelect from "@/components/SearchableSelect";
import { buildApproverOptions, fromSelectValue } from "@/lib/approvalRuleOptions";
import type { EditState } from "@/hooks/useApprovalRules";
import ApprovalFlow from "./ApprovalFlow";
import { BRAND, flowSteps, tint } from "./approvalFlowView";

interface Props {
  editing: EditState;
  workflowCount: number;
  applyAll: boolean;
  saving: boolean;
  apiError: string;
  onApplyAll: (value: boolean) => void;
  onChoice: (level: "l1_choice" | "l2_choice", value: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export default function ApprovalRuleEditor({ editing, workflowCount, applyAll, saving, apiError, onApplyAll, onChoice, onSave, onClose }: Props) {
  const l1Options = buildApproverOptions(editing.eligible, editing.l1_saved);
  const l2Options = buildApproverOptions(editing.eligible, editing.l2_saved);
  const labelOf = (options: { value: string; label: string }[], value: string) => options.find(option => option.value === value)?.label ?? "";
  const steps = flowSteps(
    { kind: fromSelectValue(editing.l1_choice).kind, label: labelOf(l1Options, editing.l1_choice) },
    { kind: fromSelectValue(editing.l2_choice).kind, label: labelOf(l2Options, editing.l2_choice) },
  );

  return (
    <section aria-label={`Edit ${editing.workflow_label}`} className="ar-editor" style={{ margin: "0 20px 18px", padding: "16px 18px", borderRadius: 16, background: tint(BRAND, 0.04), border: `1px solid ${tint(BRAND, 0.2)}` }}>
      {apiError && <div role="alert" className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {apiError}</div>}

      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--on-variant)", marginBottom: 10 }}>How a request will flow</div>
      <div style={{ marginBottom: 16 }}><ApprovalFlow steps={steps} /></div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, marginBottom: 14 }}>
        <div className="field-group" style={{ margin: 0 }}>
          <label className="field-label">L1 approver *</label>
          <SearchableSelect value={editing.l1_choice} onChange={value => onChoice("l1_choice", value)} placeholder="— Select who approves —" options={l1Options} inputClassName="field-input" />
          {!editing.l1_choice && <p className="field-error-msg">Pick who approves first. Level 1 is required.</p>}
        </div>
        <div className="field-group" style={{ margin: 0 }}>
          <label className="field-label">L2 approver <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>(leave blank for single-level)</span></label>
          <SearchableSelect value={editing.l2_choice} onChange={value => onChoice("l2_choice", value)} placeholder="— Single level (no L2) —" options={l2Options} inputClassName="field-input" />
          {editing.l2_choice && <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} onClick={() => onChoice("l2_choice", "")}><i className="ti ti-x" /> Remove level 2</button>}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        {workflowCount > 1
          ? <label className="module-check"><input type="checkbox" checked={applyAll} onChange={event => onApplyAll(event.target.checked)} /><span>Apply these approvers to all {workflowCount} workflows</span></label>
          : <span />}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={onSave} disabled={saving || !editing.l1_choice}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : applyAll ? "Save to all" : "Save Rule"}
          </button>
        </div>
      </div>
    </section>
  );
}
