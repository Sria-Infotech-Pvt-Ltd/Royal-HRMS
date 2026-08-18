"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";

interface AssessmentConfig {
  default_pass_percentage: number;
  max_attempts:            number;   // 0 = unlimited
  time_limit_mins:         number | null;
  updated_at:              string;
}

type FieldKey = "pass_percentage" | "max_attempts" | "time_limit";

interface EditState {
  field:                   FieldKey;
  default_pass_percentage: string;
  max_attempts:            string;
  time_limit_enabled:      boolean;  // UI-only, derived from time_limit_mins
  time_limit_mins:         string;
}

const FIELD_META: { key: FieldKey; icon: string; label: string; desc: string }[] = [
  { key: "pass_percentage", icon: "ti-percentage", label: "Pass Percentage",  desc: "Minimum score a candidate must achieve to pass an assessment" },
  { key: "max_attempts",    icon: "ti-refresh",    label: "Maximum Attempts", desc: "How many times a candidate can retake before being locked out (0 = unlimited)" },
  { key: "time_limit",      icon: "ti-clock",      label: "Time Limit",       desc: "Whether assessments are timed globally and the default maximum duration" },
];

function currentValue(config: AssessmentConfig, field: FieldKey): string {
  if (field === "pass_percentage") return `${config.default_pass_percentage}%`;
  if (field === "max_attempts")    return config.max_attempts === 0 ? "Unlimited" : String(config.max_attempts);
  if (field === "time_limit")      return config.time_limit_mins ? `${config.time_limit_mins} min` : "No limit";
  return "—";
}

function apiErrMsg(e: unknown) {
  return (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to save.";
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function AssessmentConfigPage() {
  const router = useRouter();
  const { data, loading, error, refetch } = useFetch<AssessmentConfig>(API.settings.assessmentConfig);

  const [editing,  setEditing]  = useState<EditState | null>(null);
  const [saving,   setSaving]   = useState(false);
  const [apiError, setApiError] = useState("");

  const config = data;

  function openEdit(field: FieldKey) {
    if (!config) return;
    setEditing({
      field,
      default_pass_percentage: String(config.default_pass_percentage),
      max_attempts:            String(config.max_attempts),
      time_limit_enabled:      config.time_limit_mins !== null,
      time_limit_mins:         config.time_limit_mins != null ? String(config.time_limit_mins) : "",
    });
    setApiError("");
  }

  async function handleSave() {
    if (!editing || !config) return;
    setSaving(true);
    setApiError("");

    let payload: Partial<Omit<AssessmentConfig, "updated_at">> = {};
    if (editing.field === "pass_percentage") {
      payload = { default_pass_percentage: Number(editing.default_pass_percentage) || 70 };
    } else if (editing.field === "max_attempts") {
      payload = { max_attempts: Number(editing.max_attempts) };
    } else {
      payload = {
        time_limit_mins: editing.time_limit_enabled && editing.time_limit_mins
          ? Number(editing.time_limit_mins) : null,
      };
    }

    try {
      await clientApi.put(API.settings.assessmentConfig, { ...config, ...payload });
      refetch();
      setEditing(null);
    } catch (err: unknown) {
      setApiError(apiErrMsg(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Assessment Config</div>
          <div className="page-sub">Global defaults for all assessments — override per-assessment in the assessment form.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-12 text-[13px] text-[var(--on-variant)]">
          <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--primary)" }} />
          Loading config…
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}

      {!loading && !error && config && (
        <>
          <div className="settings-card">
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                    <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600, width: "28%" }}>Setting</th>
                    <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600 }}>Description</th>
                    <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600, width: "14%" }}>Default Value</th>
                    <th style={{ width: 80 }} />
                  </tr>
                </thead>
                <tbody>
                  {FIELD_META.map(f => (
                    <tr key={f.key} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                      <td style={{ padding: "14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{
                            width: 32, height: 32, borderRadius: 8,
                            background: "var(--primary-c, rgba(30,78,140,0.10))",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                          }}>
                            <i className={`ti ${f.icon}`} style={{ color: "var(--primary)", fontSize: 15 }} />
                          </div>
                          <span style={{ fontWeight: 500, color: "var(--on-bg)" }}>{f.label}</span>
                        </div>
                      </td>
                      <td style={{ padding: "14px", color: "var(--on-variant)" }}>{f.desc}</td>
                      <td style={{ padding: "14px", fontWeight: 600, color: "var(--primary)" }}>
                        {currentValue(config, f.key)}
                      </td>
                      <td style={{ padding: "14px", textAlign: "right" }}>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: "4px 12px", fontSize: 12 }}
                          onClick={() => openEdit(f.key)}
                        >
                          <i className="ti ti-edit" /> Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {config.updated_at && (
            <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 10 }}>
              Last updated: {fmtDate(config.updated_at)}
            </p>
          )}
        </>
      )}

      {editing && (
        <Modal
          title={<>Edit — {FIELD_META.find(f => f.key === editing.field)?.label}</>}
          onClose={() => setEditing(null)}
          maxWidth={440}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditing(null)} disabled={saving}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save"}
              </button>
            </>
          }
        >
              {apiError && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {apiError}
                </div>
              )}

              {editing.field === "pass_percentage" && (
                <div className="field-group">
                  <label className="field-label">Default Pass Percentage *</label>
                  <input
                    type="number" min={1} max={100}
                    className="field-input"
                    value={editing.default_pass_percentage}
                    onChange={e => setEditing(p => p ? { ...p, default_pass_percentage: e.target.value } : p)}
                    placeholder="70"
                  />
                  <div style={{ fontSize: ".75rem", color: "var(--on-variant)", marginTop: 4 }}>
                    Used as default when creating a new assessment. Override per-assessment in the assessment form.
                  </div>
                </div>
              )}

              {editing.field === "max_attempts" && (
                <div className="field-group">
                  <label className="field-label">Default Maximum Attempts</label>
                  <input
                    type="number" min={0}
                    className="field-input"
                    value={editing.max_attempts}
                    onChange={e => setEditing(p => p ? { ...p, max_attempts: e.target.value } : p)}
                    placeholder="3"
                  />
                  <div style={{ fontSize: ".75rem", color: "var(--on-variant)", marginTop: 4 }}>
                    Set to <strong>0</strong> for unlimited attempts globally. Individual assessments can override this.
                  </div>
                </div>
              )}

              {editing.field === "time_limit" && (
                <>
                  <div className="field-group mb-16">
                    <label className="field-label">Global Time Limit</label>
                    <label style={{
                      display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
                      padding: "10px 12px", borderRadius: 8,
                      border: "1px solid var(--outline-v)",
                      background: "var(--surface-v, #f8fafc)",
                    }}>
                      <input
                        type="checkbox"
                        checked={editing.time_limit_enabled}
                        onChange={e => setEditing(p => p ? {
                          ...p,
                          time_limit_enabled: e.target.checked,
                          time_limit_mins: e.target.checked ? p.time_limit_mins : "",
                        } : p)}
                      />
                      <span style={{ fontSize: ".88rem", color: "var(--on-bg)" }}>
                        Enable a default time limit for assessments
                      </span>
                    </label>
                  </div>

                  {editing.time_limit_enabled && (
                    <div className="field-group">
                      <label className="field-label">Duration (minutes) *</label>
                      <input
                        type="number" min={1}
                        className="field-input"
                        value={editing.time_limit_mins}
                        onChange={e => setEditing(p => p ? { ...p, time_limit_mins: e.target.value } : p)}
                        placeholder="e.g. 30"
                      />
                      <div style={{ fontSize: ".75rem", color: "var(--on-variant)", marginTop: 4 }}>
                        Per-assessment overrides take precedence. <code>null</code> = no global limit.
                      </div>
                    </div>
                  )}
                </>
              )}
        </Modal>
      )}
    </div>
  );
}
