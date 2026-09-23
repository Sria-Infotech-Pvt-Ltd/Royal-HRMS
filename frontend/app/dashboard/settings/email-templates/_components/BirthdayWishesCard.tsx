"use client";

// Fully self-contained "Automatic Birthday Wishes" settings card — manages
// its own state and API calls (GET/PATCH API.hrms.birthdaySettings), no
// coupling to anything else on the Email Templates page. Merged in from the
// standalone Birthday Wishes settings page (the master enable toggle and
// the banner/notification copy aren't email templates, but they're the
// birthday feature's only other configurable pieces, so they live here as
// a second settings card).

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface BirthdaySettingsForm {
  is_enabled:                     boolean;
  banner_message_template:        string;
  employee_notification_template: string;
  team_notification_template:     string;
  manager_notification_template:  string;
}

const EMPTY_BIRTHDAY: BirthdaySettingsForm = {
  is_enabled:                     true,
  banner_message_template:        "",
  employee_notification_template: "",
  team_notification_template:     "",
  manager_notification_template:  "",
};

export default function BirthdayWishesCard({ showToast }: { showToast: (msg: string, ok?: boolean) => void }) {
  const [open,    setOpen]    = useState(false);
  const [form,    setForm]    = useState<BirthdaySettingsForm>(EMPTY_BIRTHDAY);
  const [base,    setBase]    = useState<BirthdaySettingsForm>(EMPTY_BIRTHDAY);
  const [saving,  setSaving]  = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res  = await clientApi.get<{ data: BirthdaySettingsForm }>(API.hrms.birthdaySettings);
        const data = res.data?.data;
        if (data) { setForm(data); setBase(data); }
      } catch { /* card just keeps showing the default form */ }
    })();
  }, []);

  async function save() {
    setSaving(true);
    try {
      const res = await clientApi.patch<{ data: BirthdaySettingsForm }>(API.hrms.birthdaySettings, form);
      const updated = res.data?.data ?? form;
      setForm(updated);
      setBase(updated);
      setOpen(false);
      showToast("Birthday wishes settings updated");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to save birthday settings", false);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setForm(base);
    setOpen(false);
  }

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", marginBottom: 24, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--outline-v)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <i className="ti ti-cake" style={{ fontSize: 16, color: "var(--primary)" }} />
          <span style={{ fontSize: 13, fontWeight: 600 }}>Automatic Birthday Wishes</span>
          <span style={{ fontSize: 11, fontWeight: 600, marginLeft: 4, color: form.is_enabled ? "var(--success)" : "var(--on-variant)" }}>
            {form.is_enabled ? "Enabled" : "Disabled"}
          </span>
        </div>
        {!open && (
          <button className="btn btn-ghost btn-sm" onClick={() => setOpen(true)} suppressHydrationWarning>
            <i className="ti ti-pencil" style={{ fontSize: 13 }} /> Edit
          </button>
        )}
      </div>

      {!open && (
        <div style={{ padding: "16px 18px", fontSize: 12, color: "var(--on-variant)", display: "flex", flexDirection: "column", gap: 6 }}>
          <span>
            Dashboard banner and notification copy shown to the employee, their team, and their manager on someone&apos;s birthday.
            The birthday <em>email</em> subject/body is edited below, in the Wish template.
          </span>
          <a href="/dashboard/settings/audit?module=birthday" style={{ color: "var(--primary)", fontWeight: 500 }}>
            <i className="ti ti-history" /> View birthday email delivery logs — Audit Log →
          </a>
        </div>
      )}

      {open && (
        <div style={{ padding: "20px 24px", borderTop: "1px solid var(--outline-v)", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="module-check">
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={e => setForm(f => ({ ...f, is_enabled: e.target.checked }))}
              />
              <span>Enable automatic birthday wishes</span>
            </label>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              When off, no birthday email, dashboard banner, or notification is sent to anyone.
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Dashboard birthday banner message</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.banner_message_template}
              onChange={e => setForm(f => ({ ...f, banner_message_template: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Shown under &quot;Happy Birthday, [Name]!&quot; on every employee&apos;s dashboard, company-wide, whenever it&apos;s someone&apos;s birthday.
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Employee in-app notification text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.employee_notification_template}
              onChange={e => setForm(f => ({ ...f, employee_notification_template: e.target.value }))}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Teammate notification / card text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.team_notification_template}
              onChange={e => setForm(f => ({ ...f, team_notification_template: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Use <code>{"{employee_name}"}</code> as a placeholder — shown to teammates sharing the same reporting manager.
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Manager notification / card text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.manager_notification_template}
              onChange={e => setForm(f => ({ ...f, manager_notification_template: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Use <code>{"{employee_name}"}</code> as a placeholder — shown to the employee&apos;s reporting manager.
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-ghost btn-sm" onClick={cancel} disabled={saving} suppressHydrationWarning>Cancel</button>
            <button className="btn btn-filled btn-sm" onClick={save} disabled={saving} suppressHydrationWarning>
              {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : "Save Birthday Settings"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
