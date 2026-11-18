"use client";

// The global approval rules, the editor for one of them, "apply to all workflows", and Undo for the last save. Saving one rule sends the
// same request as before; applying to all sends it once per workflow and reports any workflow the server refused.

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { fromSelectValue, toSelectValue } from "@/lib/approvalRuleOptions";
import type { ApprovalRulePerson, ApprovalWorkflowType, GlobalApprovalRule } from "@/types/approvalMatrix";

export interface EditState {
  workflow_type:  ApprovalWorkflowType;
  workflow_label: string;
  /** Dropdown values: "reporting_manager", "hr", "person:<id>" or "". */
  l1_choice:      string;
  l2_choice:      string;
  eligible:       ApprovalRulePerson[];
  l1_saved:       { userId: string | null; label: string } | null;
  l2_saved:       { userId: string | null; label: string } | null;
}

/** What to put back to undo a save: the dropdown values each workflow had before. */
export interface LastChange { labels: string[]; previous: { workflow_type: ApprovalWorkflowType; l1: string; l2: string }[] }

const messageOf = (err: unknown, fallback: string): string => (err as { response?: { data?: { message?: string } } })?.response?.data?.message || fallback;

export function useApprovalRules() {
  const { data, loading, error, refetch } = useFetch<GlobalApprovalRule[]>(API.settings.approvalRules);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [applyAll, setApplyAll] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");
  const [lastChange, setLastChange] = useState<LastChange | null>(null);
  const rules = data ?? [];

  function openEdit(rule: GlobalApprovalRule) {
    setEditing({
      workflow_type:  rule.workflow_type,
      workflow_label: rule.workflow_label,
      l1_choice:      toSelectValue(rule.l1_approver_kind, rule.l1_approver_user_id),
      l2_choice:      toSelectValue(rule.l2_approver_kind, rule.l2_approver_user_id),
      eligible:       rule.eligible_approvers ?? [],
      l1_saved:       { userId: rule.l1_approver_user_id, label: rule.l1_approver_label },
      l2_saved:       { userId: rule.l2_approver_user_id, label: rule.l2_approver_label },
    });
    setApplyAll(false);
    setApiError("");
  }

  const closeEdit = () => { setEditing(null); setApplyAll(false); };

  function setChoice(level: "l1_choice" | "l2_choice", value: string) {
    setEditing(previous => previous ? { ...previous, [level]: value } : previous);
  }

  const sendRule = (type: ApprovalWorkflowType, l1Choice: string, l2Choice: string) => {
    const l1 = fromSelectValue(l1Choice);
    const l2 = fromSelectValue(l2Choice);
    return clientApi.patch(API.settings.approvalRules, { workflow_type: type, l1_approver_kind: l1.kind, l1_approver_user: l1.userId, l2_approver_kind: l2.kind, l2_approver_user: l2.userId });
  };

  async function save() {
    if (!editing) return;
    setSaving(true);
    setApiError("");
    const targets = applyAll ? rules : rules.filter(rule => rule.workflow_type === editing.workflow_type);
    const done: LastChange = { labels: [], previous: [] };
    const refused: string[] = [];
    for (const rule of targets) {
      try {
        await sendRule(rule.workflow_type, editing.l1_choice, editing.l2_choice);
        done.labels.push(rule.workflow_label);
        done.previous.push({ workflow_type: rule.workflow_type, l1: toSelectValue(rule.l1_approver_kind, rule.l1_approver_user_id), l2: toSelectValue(rule.l2_approver_kind, rule.l2_approver_user_id) });
      } catch (err: unknown) {
        refused.push(applyAll ? `${rule.workflow_label}: ${messageOf(err, "Failed to save rule.")}` : messageOf(err, "Failed to save rule."));
      }
    }
    if (done.previous.length > 0) { refetch(); setLastChange(done); }
    if (refused.length === 0) closeEdit(); else setApiError(refused.join(" "));
    setSaving(false);
  }

  async function undo() {
    if (!lastChange) return;
    const change = lastChange;
    setLastChange(null);
    try {
      for (const entry of change.previous) await sendRule(entry.workflow_type, entry.l1, entry.l2);
    } catch (err: unknown) {
      setApiError(messageOf(err, "Could not undo the change."));
    }
    refetch();
  }

  return { rules, loading, error, editing, applyAll, setApplyAll, saving, apiError, lastChange, dismissChange: () => setLastChange(null), openEdit, closeEdit, setChoice, save, undo };
}
