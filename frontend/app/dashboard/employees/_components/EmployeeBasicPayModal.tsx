"use client";

// "Basic pay" from the employee drawer — the reference's pay dialog: validity, pay scale, the monthly
// earnings / employer-contribution / statutory-deduction breakup (derived from the CTC, any earning can be
// overridden), the employee's declarations, and the effective-dated record history. Holders of payroll.edit
// (Payroll Admin) can change and save it; everyone else sees it read-only. The server enforces the permission.

import RefModal from "@/components/employees/RefModal";
import { useT } from "@/hooks/useI18n";
import { usePermission } from "@/hooks/usePermission";
import { PAY_REASONS, useBasicPayEditor } from "@/hooks/useBasicPayEditor";
import { formatDateSlash } from "@/lib/formatDate";
import { fullName, type Employee } from "../_data";
import PayBreakupTables from "./PayBreakupTables";
import DateInput from "@/components/shared/DateInput";

const inr = (value: string | number) => `₹${Math.round(Number(value) || 0).toLocaleString("en-IN")}`;
const dayBefore = (iso: string) => {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() - 1);
  return date.toISOString().slice(0, 10);
};
const TAX_REGIME_LABEL = { new: "New regime (115BAC)", old: "Old regime", "": "New regime (115BAC)" } as const;

export default function EmployeeBasicPayModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const t = useT();
  const canEdit = usePermission("payroll.edit");
  const editor = useBasicPayEditor(employee, onClose);
  const { form, current, rows, breakup } = editor;
  const orgUnit = editor.detail?.org_unit_name || employee.orgUnitName || employee.department || "Corporate";
  const hasBank = !!editor.detail?.profile?.account_number_masked;

  const subtitle = current
    ? t("{name} · {code} — record valid from {date} to 31/12/9999.", { name: fullName(employee), code: employee.code, date: formatDateSlash(current.effective_from) })
    : t("{name} · {code} — no pay record yet.", { name: fullName(employee), code: employee.code });

  return (
    <RefModal
      title={t("Basic")} accent={t("pay")} subtitle={subtitle} onClose={onClose} closeDisabled={editor.saving}
      note={
        canEdit
          ? <span style={editor.delimitIsError ? { color: "var(--crit)" } : undefined}>{editor.formError || editor.delimitNote}</span>
          : <span><i className="ti ti-lock" /> {t("Pay records are maintained by Payroll. You can view this record but not change it.")}</span>
      }
      actions={
        <>
          <button className="rvbtn ghost" type="button" onClick={onClose} disabled={editor.saving}>{canEdit ? t("Cancel") : t("Close")}</button>
          {canEdit && (
            <button className="rvbtn pri" type="button" onClick={editor.save} disabled={editor.saving || editor.loading || editor.delimitIsError || !editor.hasStructure}>
              {editor.saving ? t("Saving…") : t("Save basic pay")}
            </button>
          )}
        </>
      }
    >
      {editor.loadError && <div className="alert alert-error">{editor.loadError}</div>}
      {!editor.loading && !editor.hasStructure && (
        <div className="alert alert-warn">{t("No salary structure applies to this employee. Add or activate one in Settings → Payroll Configuration → Salary Structures; pay components come from it.")}</div>
      )}
      <div className="legend">
        <b style={{ fontSize: 10, letterSpacing: ".07em", color: "var(--faint)" }}>{t("WHO MAINTAINS")}</b>
        <span><span className="own hr">HR</span> {t("pay structure and amounts")}</span>
        <span><span className="own emp">{t("HR / EMPLOYEE")}</span> {t("employee may self-declare")}</span>
        <span><span className="own adm">{t("ADMIN")}</span> {t("system configuration, locked")}</span>
      </div>

      <div className="sechead">{t("VALIDITY")} <span className="own hr">HR</span></div>
      <div className="g3">
        <div className="f">
          <label>{t("Start date")} <span className="req">*</span></label>
          <DateInput className="finput" value={form.effectiveFrom} disabled={!canEdit} onChange={isoDate => form.setEffectiveFrom(isoDate)} />
        </div>
        <div className="f"><label>{t("End date")}</label><input className="finput auto" disabled value="31/12/9999" readOnly /></div>
        <div className="f">
          <label>{t("Reason for change")}</label>
          <select className="finput" value={form.reason} disabled={!canEdit} onChange={event => form.setReason(event.target.value as typeof form.reason)}>
            {PAY_REASONS.map(option => <option key={option.value} value={option.value}>{t(option.label)}</option>)}
          </select>
        </div>
      </div>

      <div className="sechead">{t("PAY SCALE & PAYROLL AREA")} <span className="own adm">{t("ADMIN")}</span></div>
      <div className="g3">
        <div className="f"><label>{t("Payroll area")}</label><input className="finput auto" disabled readOnly value={t("IN01 — India Monthly")} /></div>
        <div className="f"><label>{t("Pay scale type")}</label><input className="finput auto" disabled readOnly value={t("IT Services — {unit}", { unit: orgUnit })} /></div>
        <div className="f"><label>{t("ES grouping / CAP %")}</label><input className="finput auto" disabled readOnly value="ESG 3 · 100%" /></div>
      </div>
      <div className="g3">
        <div className="f">
          <label>{t("Pay scale group")} <span className="own hr">HR</span></label>
          <select className="finput" value={form.group} disabled={!canEdit} onChange={event => form.setGroup(event.target.value)}>
            {["L1", "L2", "L3", "L4", "L5"].map(value => <option key={value}>{value}</option>)}
          </select>
        </div>
        <div className="f">
          <label>{t("Pay scale level")} <span className="own hr">HR</span></label>
          <select className="finput" value={form.level} disabled={!canEdit} onChange={event => form.setLevel(event.target.value)}>
            {["01", "02", "03", "04"].map(value => <option key={value}>{value}</option>)}
          </select>
        </div>
        <div className="f">
          <label>{t("Salary structure")} <span className="own hr">HR</span></label>
          <select
            className="finput"
            value={form.salaryStructureId}
            disabled={!canEdit || editor.structures.length === 0}
            onChange={event => form.setSalaryStructure(event.target.value)}
          >
            <option value="">{t("Select a salary structure")}</option>
            {editor.structures.map(structure => (
              <option key={structure.id} value={structure.id}>
                {structure.is_default ? t("{name} (Default)", { name: structure.name }) : structure.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="g3">
        <div className="f">
          <label>{t("Annual fixed CTC (₹)")} <span className="req">*</span> <span className="own hr">HR</span></label>
          <input className="finput" type="number" min={0} step={1000} value={form.annualCtc} disabled={!canEdit} placeholder={t("e.g. 900000")} onChange={event => form.setAnnualCtc(event.target.value)} />
        </div>
      </div>

      <div className="hint">
        {t("Monthly amounts use the selected salary structure and effective date. Enabled structure components appear here; statutory contributions and deductions remain governed by payroll eligibility and statutory rules.")}
      </div>
      <PayBreakupTables
        breakup={breakup}
        annualCostToCompany={editor.annualCostToCompany}
        editable={canEdit}
        variance={editor.variance}
        hasRecord={!!current}
        visibleLineCodes={editor.visiblePayLineCodes}
        onChange={editor.setOverride}
      />
      {canEdit && (
        <div>
          <button className="rvbtn" type="button" onClick={editor.resetOverrides} disabled={!editor.hasOverrides}>{t("Reset to derived amounts")}</button>
        </div>
      )}

      <div className="sechead">{t("EMPLOYEE DECLARATIONS")} <span className="own emp">{t("HR / EMPLOYEE")}</span></div>
      <div className="g3">
        <div className="f">
          <label>{t("Tax regime")}</label>
          <select className="finput" disabled value={current?.employee_tax_regime ?? ""} onChange={() => undefined}>
            <option value="">{t(TAX_REGIME_LABEL[""])}</option>
            <option value="new">{t(TAX_REGIME_LABEL.new)}</option>
            <option value="old">{t(TAX_REGIME_LABEL.old)}</option>
          </select>
          <div className="hint">{t("Employee elects once per financial year.")}</div>
        </div>
        <div className="f"><label>{t("Salary bank account")}</label><input className="finput auto" disabled readOnly value={hasBank ? t("On file — masked") : t("From statutory section")} /></div>
        <div className="f"><label>{t("Payment method")}</label><input className="finput auto" disabled readOnly value={t("Bank transfer – NEFT")} /></div>
      </div>

      <div className="sechead">{t("RECORD HISTORY")}</div>
      {rows.length === 0 ? (
        <div className="hint">{t("No pay record exists for this employee yet.")}</div>
      ) : (
        rows.map((row, index) => {
          const next = rows[index - 1];
          return (
            <div key={row.id} className={`actrow${row.is_active ? " live" : ""}`}>
              <span className="bar" />
              <div className="meta">
                <div className="t1">{inr(row.annual_ctc)} {t("p.a.")}{row.is_active && <span className="chip ok">{t("Current")}</span>}</div>
                <div className="t2">{row.reason_display || "—"} · {t("scale {group}/{level}", { group: row.pay_scale_group || "—", level: row.pay_scale_level || "—" })}</div>
              </div>
              <div className="dates" style={{ textAlign: "right" }}>
                {formatDateSlash(row.effective_from)}
                <div className="actdel">{t("to {date}", { date: next ? formatDateSlash(dayBefore(next.effective_from)) : "31/12/9999" })}</div>
              </div>
            </div>
          );
        })
      )}
    </RefModal>
  );
}
