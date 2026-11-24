"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useT } from "@/hooks/useI18n";
import { useApprovalRules } from "@/hooks/useApprovalRules";
import ApprovalRulesList from "./_components/ApprovalRulesList";
import { BRAND, summarise, tint } from "./_components/approvalFlowView";

export default function ApprovalRulesPage() {
  const router = useRouter();
  const t = useT();
  const approval = useApprovalRules();
  const { rules, loading, error, lastChange } = approval;
  const totals = summarise(rules);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Approval Rules")}</div>
          <div className="page-sub">{t("Who approves each workflow, for everyone. Individual employees can have their own override on their profile.")}</div>
        </div>
        <div className="page-actions">
          <Link href="/dashboard/settings/audit?module=settings" className="btn btn-ghost"><i className="ti ti-history" /> {t("Change history")}</Link>
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> {t("Back")}
          </button>
        </div>
      </div>

      {error && <div role="alert" className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      {lastChange && (
        <div role="status" style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 12, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 13, background: tint(BRAND, 0.08), border: `1px solid ${tint(BRAND, 0.25)}` }}>
          <i className="ti ti-circle-check" aria-hidden="true" style={{ color: BRAND, fontSize: 18 }} />
          <span style={{ flex: 1 }}>{t("Saved for {labels}.", { labels: lastChange.labels.join(", ") })}</span>
          <button className="btn btn-ghost btn-sm" onClick={approval.undo}><i className="ti ti-arrow-back-up" /> {t("Undo")}</button>
          <button className="btn btn-ghost btn-sm" aria-label={t("Dismiss")} onClick={approval.dismissChange}><i className="ti ti-x" /></button>
        </div>
      )}

      {!error && (
        <>
          {!loading && (
            <p aria-label={t("Summary")} style={{ margin: "0 0 14px", fontSize: 13, color: "var(--on-variant)" }}>
              <b style={{ color: "var(--on-bg)" }}>{totals.workflows}</b> {t("workflows")} · <b style={{ color: "var(--on-bg)" }}>{totals.twoLevel}</b> {t("two-level")} · <b style={{ color: "var(--on-bg)" }}>{totals.oneLevel}</b> {t("single-level")} · <b style={{ color: "var(--on-bg)" }}>{totals.namedPeople}</b> {totals.namedPeople === 1 ? t("named person") : t("named people")}
            </p>
          )}

          {!loading && totals.unset > 0 && (
            <div role="alert" style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 12, fontSize: 13, color: "var(--on-bg)", background: tint("#EA580C", 0.08), border: `1px solid ${tint("#EA580C", 0.28)}` }}>
              <i className="ti ti-alert-triangle" aria-hidden="true" style={{ color: "#EA580C" }} /> {totals.unset === 1 ? t("{count} workflow has no level 1 approver yet. Requests of that kind have nobody to approve them.", { count: totals.unset }) : t("{count} workflows have no level 1 approver yet. Requests of that kind have nobody to approve them.", { count: totals.unset })}
            </div>
          )}

          <ApprovalRulesList
            rules={rules} loading={loading} editing={approval.editing} applyAll={approval.applyAll} saving={approval.saving} apiError={approval.apiError}
            onEdit={approval.openEdit} onClose={approval.closeEdit} onApplyAll={approval.setApplyAll} onChoice={approval.setChoice} onSave={approval.save}
          />
        </>
      )}
    </div>
  );
}
