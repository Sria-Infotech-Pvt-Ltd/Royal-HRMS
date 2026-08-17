"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import ToggleSwitch from "@/components/ToggleSwitch";
import { usePermission } from "@/hooks/usePermission";

interface NotificationSettingsForm {
  is_leave_enabled:      boolean;
  is_expense_enabled:    boolean;
  is_separation_enabled: boolean;
  is_payroll_enabled:    boolean;
  is_approval_enabled:   boolean;
  is_document_enabled:   boolean;
  is_attendance_enabled: boolean;
  is_system_enabled:     boolean;
}

const DEFAULT_SETTINGS: NotificationSettingsForm = {
  is_leave_enabled:      true,
  is_expense_enabled:    true,
  is_separation_enabled: true,
  is_payroll_enabled:    true,
  is_approval_enabled:   true,
  is_document_enabled:   true,
  is_attendance_enabled: true,
  is_system_enabled:     true,
};

const CATEGORIES: { field: keyof NotificationSettingsForm; icon: string; label: string; desc: string }[] = [
  { field: "is_leave_enabled",      icon: "ti-beach",           label: "Leave Notifications",       desc: "Receive notifications for leave requests, approvals, and rejections." },
  { field: "is_expense_enabled",    icon: "ti-receipt",         label: "Expense Notifications",      desc: "Receive notifications for expense submissions, approvals, and rejections." },
  { field: "is_separation_enabled", icon: "ti-door-exit",       label: "Separation Notifications",   desc: "Receive notifications for separation requests, approvals, rejections, and status updates." },
  { field: "is_payroll_enabled",    icon: "ti-report-money",    label: "Payroll Notifications",      desc: "Receive notifications for payslip generation and payroll updates." },
  { field: "is_approval_enabled",   icon: "ti-checkbox",        label: "Approval Notifications",     desc: "Receive notifications when an action requires your approval." },
  { field: "is_document_enabled",   icon: "ti-file-text",       label: "Document Notifications",     desc: "Receive notifications when documents are uploaded or require action." },
  { field: "is_attendance_enabled", icon: "ti-clock",           label: "Attendance Notifications",   desc: "Receive notifications for attendance-related actions or issues." },
  { field: "is_system_enabled",     icon: "ti-server",          label: "System Notifications",       desc: "Receive important HRMS system notifications." },
];

export default function NotificationsConfigPage() {
  const router  = useRouter();
  const canEdit = usePermission("settings.edit");

  const [settings,     setSettings]     = useState<NotificationSettingsForm>(DEFAULT_SETTINGS);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [savingField,  setSavingField]  = useState<string | null>(null);
  const [toast,        setToast]        = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { loadSettings(); }, []);

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const res  = await clientApi.get<{ data: NotificationSettingsForm }>(API.notifications.settings);
      const data = res.data?.data;
      if (data) setSettings(data);
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? "Failed to load notification settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(field: keyof NotificationSettingsForm, checked: boolean) {
    const previous = settings;
    setSettings(prev => ({ ...prev, [field]: checked }));
    setSavingField(field);
    try {
      const res = await clientApi.patch<{ data: NotificationSettingsForm }>(API.notifications.settings, { [field]: checked });
      const updated = res.data?.data;
      if (updated) setSettings(updated);
      showToast("Notification settings updated");
    } catch (err: unknown) {
      setSettings(previous);
      showToast((err as { message?: string }).message ?? "Failed to update notification settings", false);
    } finally {
      setSavingField(null);
    }
  }

  return (
    <>
      {toast && (
        <div style={{ position: "fixed", top: 16, right: 20, zIndex: 9999, display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", background: toast.ok ? "var(--success-c)" : "var(--error-c)", border: `1px solid ${toast.ok ? "var(--success)" : "var(--error)"}`, borderRadius: "var(--radius)", boxShadow: "var(--shadow-md)", fontSize: 13, color: toast.ok ? "var(--success)" : "var(--error)" }}>
          <i className={`ti ${toast.ok ? "ti-circle-check" : "ti-alert-circle"}`} style={{ fontSize: 16 }} />
          {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <div className="page-title">Notification Settings</div>
          <div className="page-sub">Manage which HRMS notifications users receive.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")} suppressHydrationWarning>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 260, gap: 10, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} /> Loading notification settings…
        </div>
      )}

      {!loading && error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>Failed to load</strong> — {error}
            <div style={{ marginTop: 8 }}><button className="btn btn-ghost btn-sm" onClick={loadSettings} suppressHydrationWarning>Retry</button></div>
          </div>
        </div>
      )}

      {!loading && !error && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", overflow: "hidden" }}>
          {CATEGORIES.map((cat, idx) => (
            <div
              key={cat.field}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
                padding: "16px 18px",
                borderBottom: idx !== CATEGORIES.length - 1 ? "1px solid var(--outline-v)" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: "var(--outline-v)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <i className={`ti ${cat.icon}`} style={{ fontSize: 16, color: "var(--primary)" }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{cat.label}</div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>{cat.desc}</div>
                </div>
              </div>
              <ToggleSwitch
                checked={settings[cat.field]}
                onChange={checked => handleToggle(cat.field, checked)}
                disabled={!canEdit || savingField === cat.field}
              />
            </div>
          ))}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </>
  );
}
