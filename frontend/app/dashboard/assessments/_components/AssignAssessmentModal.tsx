import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import type { Assessment, AssignEmployee, EmailTemplateOption } from "../_types";

interface AssignAssessmentModalProps {
  assignFor: Assessment;
  onClose: () => void;
  assignCids: string[];
  toggleAssignCid: (id: string) => void;
  toggleSelectAll: () => void;
  assignSearch: string;
  setAssignSearch: (v: string) => void;
  assignTemplate: string;
  setAssignTemplate: (v: string) => void;
  emailTemplateOptions: EmailTemplateOption[] | null | undefined;
  assignCandidates: AssignEmployee[];
  filteredCandidates: AssignEmployee[];
  assigning: boolean;
  assignErr: string;
  assignOk: string;
  doAssign: () => void;
}

export default function AssignAssessmentModal({
  assignFor, onClose, assignCids, toggleAssignCid, toggleSelectAll,
  assignSearch, setAssignSearch, assignTemplate, setAssignTemplate,
  emailTemplateOptions, assignCandidates, filteredCandidates,
  assigning, assignErr, assignOk, doAssign,
}: AssignAssessmentModalProps) {
  const t = useT();
  return (
    <Modal
      title={t("Assign — {title}", { title: assignFor.title })}
      onClose={onClose}
      maxWidth={500}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Close")}</button>
          <button className="btn btn-primary" onClick={doAssign} disabled={assigning || assignCids.length === 0}>
            {assigning
              ? <><i className="ti ti-loader-2 spin" /> {t("Assigning…")}</>
              : <><i className="ti ti-user-plus" /> {assignCids.length > 1 ? t("Assign ({count})", { count: assignCids.length }) : t("Assign")}</>}
          </button>
        </>
      }
    >
          {assignErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{assignErr}</div></div>}
          {assignOk  && <div className="alert alert-success mb-12"><i className="ti ti-check" /><div>{assignOk}</div></div>}

          {/* Notification template */}
          <div className="field-group mb-12">
            <label className="field-label">{t("Notification Email Template")}</label>
            <select
              className="field-input field-select"
              value={assignTemplate}
              onChange={e => setAssignTemplate(e.target.value)}
            >
              {!emailTemplateOptions || emailTemplateOptions.length === 0 ? (
                <option value="assessment_assigned">{t("Assessment Assigned (default)")}</option>
              ) : (
                emailTemplateOptions.map(option => (
                  <option key={option.name} value={option.name}>{option.display_name}</option>
                ))
              )}
            </select>
          </div>

          {/* Search */}
          <div className="field-group mb-8">
            <div style={{ position: "relative" }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 14, pointerEvents: "none" }} />
              <input
                className="field-input"
                style={{ paddingLeft: 32 }}
                placeholder={t("Search by name, email or ID…")}
                value={assignSearch}
                onChange={e => setAssignSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Select All / count */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
            <button
              className="btn btn-ghost"
              style={{ fontSize: 12, padding: "2px 8px" }}
              onClick={toggleSelectAll}
              disabled={filteredCandidates.length === 0}
            >
              {assignCids.length === filteredCandidates.length && filteredCandidates.length > 0 ? t("Deselect All") : t("Select All")}
            </button>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              {t("{selected} selected · {shown} shown", { selected: assignCids.length, shown: filteredCandidates.length })}
            </span>
          </div>

          {/* Employee checklist */}
          <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
            {filteredCandidates.length === 0 && (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                {assignCandidates.length === 0 ? <><i className="ti ti-loader-2 spin mr-6" />{t("Loading…")}</> : t("No employees match.")}
              </div>
            )}
            {filteredCandidates.map((e, idx) => {
              const checked = assignCids.includes(e.id);
              return (
                <label
                  key={e.id}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "9px 12px", cursor: "pointer",
                    borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                    background: checked ? "var(--primary-c, color-mix(in srgb, var(--brand) 7%, transparent))" : "transparent",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleAssignCid(e.id)}
                    style={{ flexShrink: 0 }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{e.full_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{e.employee_id} · {e.email}{e.department ? ` · ${e.department}` : ""}</div>
                  </div>
                </label>
              );
            })}
          </div>
    </Modal>
  );
}
