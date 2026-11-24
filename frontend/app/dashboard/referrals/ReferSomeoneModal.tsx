"use client";

import Modal from "@/components/Modal";
import SearchableSelect from "@/components/SearchableSelect";
import type { Branch } from "@/app/dashboard/interview-list/_data";
import { RELATIONSHIP_OPTIONS, EMPTY_FORM } from "./_data";
import { useT } from "@/hooks/useI18n";

interface ReferSomeoneModalProps {
  form: typeof EMPTY_FORM;
  setField: (key: keyof typeof EMPTY_FORM, value: string) => void;
  formError: string;
  saving: boolean;
  isAdmin: boolean;
  myBranch: string;
  branches: Branch[];
  onSubmit: (e: { preventDefault(): void }) => void;
  onClose: () => void;
}

export default function ReferSomeoneModal({
  form, setField, formError, saving, isAdmin, myBranch, branches, onSubmit, onClose,
}: ReferSomeoneModalProps) {
  const t = useT();
  return (
    <Modal
      title={<>{t("Refer Someone")}<div style={{ fontSize: 12, color: "var(--on-variant)", margin: 0, fontWeight: 400 }}>{t("Share a great candidate and earn a referral bonus")}</div></>}
      onClose={onClose}
      size="lg"
      maxWidth={680}
    >
          {formError && (
            <div className="alert alert-error" style={{ marginBottom: 20 }}>
              <i className="ti ti-alert-circle" /><div>{formError}</div>
            </div>
          )}

          <form onSubmit={onSubmit}>
            <p style={{ fontWeight: 700, fontSize: 11, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 16 }}>
              {t("Candidate Information")}
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 20px", marginBottom: 16 }}>
              <div className="field-group">
                <label className="field-label">{t("Full Name")} <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder={t("e.g. Rahul Sharma")}
                  value={form.name} onChange={e => setField("name", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Email Address")} <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="email" className="field-input" placeholder="candidate@email.com"
                  value={form.email} onChange={e => setField("email", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Phone Number")}</label>
                <input className="field-input" placeholder="+91 9876543210"
                  value={form.phone} onChange={e => setField("phone", e.target.value)}
                  suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Position Applied For")} <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder={t("e.g. Senior Developer")}
                  value={form.position_applied} onChange={e => setField("position_applied", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Company Code")}{isAdmin && <span style={{ color: "var(--error)" }}> *</span>}</label>
                {isAdmin ? (
                  <SearchableSelect
                    inputClassName="field-input"
                    value={form.branch}
                    onChange={v => setField("branch", v)}
                    placeholder={t("Select Company Code…")}
                    options={branches.map(b => ({ value: String(b.id), label: b.branch_name }))}
                  />
                ) : (
                  <div className="field-input" style={{ background: "var(--bg-mid)", color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 8, cursor: "default" }}>
                    <i className="ti ti-building" style={{ fontSize: 14, flexShrink: 0 }} />
                    {myBranch || t("Not assigned")}
                  </div>
                )}
              </div>
              <div className="field-group">
                <label className="field-label">{t("Your Relationship")} <span style={{ color: "var(--error)" }}>*</span></label>
                <select className="field-input field-select"
                  value={form.relationship} onChange={e => setField("relationship", e.target.value)}
                  required suppressHydrationWarning>
                  <option value="">{t("Select relationship")}</option>
                  {RELATIONSHIP_OPTIONS.map(r => <option key={r} value={r}>{t(r)}</option>)}
                </select>
              </div>
            </div>
            <div className="field-group" style={{ marginBottom: 20 }}>
              <label className="field-label">{t("Why would they be a great fit?")}</label>
              <textarea className="field-input" rows={3}
                placeholder={t("Share their experience, skills, and why you're recommending them…")}
                value={form.notes} onChange={e => setField("notes", e.target.value)}
                suppressHydrationWarning style={{ resize: "vertical" }} />
            </div>
            <div className="alert alert-info" style={{ marginBottom: 20 }}>
              <i className="ti ti-info-circle" />
              <div>{t("By submitting this referral you confirm the candidate has consented to share their information and has not applied in the last 12 months.")}</div>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <button type="submit" className="btn btn-filled" disabled={saving} suppressHydrationWarning>
                {saving ? <><i className="ti ti-loader-2 spin" /> {t("Submitting…")}</> : <><i className="ti ti-send" /> {t("Submit Referral")}</>}
              </button>
              <button type="button" className="btn btn-ghost" onClick={onClose} suppressHydrationWarning>
                {t("Cancel")}
              </button>
            </div>
          </form>
    </Modal>
  );
}
