"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface BirthdaySettings {
  is_enabled:                     boolean;
  banner_message_template:        string;
  employee_notification_template: string;
  team_notification_template:     string;
  manager_notification_template:  string;
}

const EMPTY: BirthdaySettings = {
  is_enabled:                     true,
  banner_message_template:        "",
  employee_notification_template: "",
  team_notification_template:     "",
  manager_notification_template:  "",
};

export default function BirthdayWishesSettingsPage() {
  const router = useRouter();

  const [form,     setForm]     = useState<BirthdaySettings>(EMPTY);
  const [base,     setBase]     = useState<BirthdaySettings>(EMPTY);
  const [loading,  setLoading]  = useState(true);
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    clientApi
      .get<{ data: BirthdaySettings }>(API.hrms.birthdaySettings)
      .then(({ data }) => {
        const d = data.data;
        setForm(d);
        setBase(d);
      })
      .catch(() => setApiError("Failed to load birthday settings."))
      .finally(() => setLoading(false));
  }, []);

  const dirty = JSON.stringify(form) !== JSON.stringify(base);

  function onField(key: keyof BirthdaySettings, value: string | boolean) {
    setSaved(false);
    setApiError(null);
    setForm(f => ({ ...f, [key]: value }));
  }

  async function onSave() {
    setSaving(true);
    setApiError(null);
    try {
      const { data } = await clientApi.patch<{ data: BirthdaySettings }>(
        API.hrms.birthdaySettings, form,
      );
      setForm(data.data);
      setBase(data.data);
      setSaved(true);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } };
      setApiError(apiErr?.response?.data?.message ?? "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading settings…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Birthday Wishes</div>
          <div className="page-sub">Enable automatic birthday wishes and customize the dashboard/notification copy</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled" onClick={onSave} disabled={saving || !dirty}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>
            }
          </button>
        </div>
      </div>

      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /><div>{apiError}</div>
        </div>
      )}
      {saved && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" /><div>Birthday settings saved successfully.</div>
        </div>
      )}

      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-cake" /> Automatic Birthday Wishes</div>
        </div>
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>

          <div className="field-group">
            <label className="module-check">
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={e => onField("is_enabled", e.target.checked)}
              />
              <span>Enable automatic birthday wishes</span>
            </label>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              When off, no birthday email, dashboard banner, or notification is sent to anyone.
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Dashboard birthday banner message</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.banner_message_template}
              onChange={e => onField("banner_message_template", e.target.value)}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Shown under &quot;Happy Birthday, [Name]!&quot; on every employee&apos;s dashboard, company-wide, whenever it&apos;s someone&apos;s birthday.
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Employee in-app notification text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.employee_notification_template}
              onChange={e => onField("employee_notification_template", e.target.value)}
            />
          </div>

          <div className="field-group">
            <label className="field-label">Teammate notification / card text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.team_notification_template}
              onChange={e => onField("team_notification_template", e.target.value)}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Use <code>{"{employee_name}"}</code> as a placeholder — shown to teammates sharing the same reporting manager.
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Manager notification / card text</label>
            <textarea
              className="field-input"
              rows={2}
              value={form.manager_notification_template}
              onChange={e => onField("manager_notification_template", e.target.value)}
            />
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Use <code>{"{employee_name}"}</code> as a placeholder — shown to the employee&apos;s reporting manager.
            </div>
          </div>

        </div>
      </div>

      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-link" /> Related Settings</div>
        </div>
        <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 10 }}>
          <a href="/dashboard/settings/email-templates" style={{ fontSize: 13, color: "var(--primary)", fontWeight: 500 }}>
            <i className="ti ti-mail" /> Edit the birthday email subject/body — Email Templates →
          </a>
          <a href="/dashboard/settings/audit?module=birthday" style={{ fontSize: 13, color: "var(--primary)", fontWeight: 500 }}>
            <i className="ti ti-history" /> View birthday email delivery logs — Audit Log →
          </a>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
