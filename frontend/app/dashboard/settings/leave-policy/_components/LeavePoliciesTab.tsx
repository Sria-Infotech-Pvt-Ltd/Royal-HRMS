"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import ToggleSwitch from "@/components/ToggleSwitch";
import EligibilitySection from "./EligibilitySection";

// Full shape of GET /leave/policy/ list items — includes both the existing
// Leave Types fields (annual_days, can_carry_forward, ...) and the policy
// rule fields this tab edits. This tab never reads/writes the Leave Types
// fields — those stay exclusively owned by PolicyTab.tsx.
export interface LeavePolicy {
  id:                  number;
  leave_type:          string;
  leave_type_display:  string;
  annual_days:         string;
  can_carry_forward:   boolean;
  max_carry_forward_days: number;
  policy_note:         string;
  is_active:           boolean;

  minimum_leave_duration:   string;
  maximum_leave_duration:   number;
  maximum_consecutive_days: number;
  minimum_notice_period:    number;
  allow_half_day:           boolean;
  allow_backdated_leave:    boolean;
  maximum_backdated_days:   number;
  allow_future_leave:       boolean;
  maximum_future_days:      number;

  sandwich_leave_enabled:  boolean;
  count_holidays_as_leave: boolean;
  count_weekoffs_as_leave: boolean;

  applicable_branches:         string[];
  applicable_departments:      string[];
  applicable_designations:     string[];
  applicable_employment_types: string[];
  applicable_gender:           string;
  minimum_service_period:      number;

  attachment_required:            boolean;
  medical_certificate_required:   boolean;
  medical_certificate_after_days: number;

  allow_negative_balance:    boolean;
  convert_to_lop:            boolean;
  allow_leave_cancellation:  boolean;
  cancellation_allowed_until: number;

  allow_probation_leave:     boolean;
  allow_notice_period_leave: boolean;
  allow_leave_extension:     boolean;
  allow_leave_combination:   boolean;

  updated_at: string;
}

// Exactly the fields this tab edits and PUTs back — never annual_days,
// carry-forward, policy_note, or is_active (Leave Types tab owns those).
export interface PolicyRuleFields {
  minimum_leave_duration:   number;
  maximum_leave_duration:   number;
  maximum_consecutive_days: number;
  minimum_notice_period:    number;
  allow_half_day:           boolean;
  allow_backdated_leave:    boolean;
  maximum_backdated_days:   number;
  allow_future_leave:       boolean;
  maximum_future_days:      number;

  sandwich_leave_enabled:  boolean;
  count_holidays_as_leave: boolean;
  count_weekoffs_as_leave: boolean;

  applicable_branches:         string[];
  applicable_departments:      string[];
  applicable_designations:     string[];
  applicable_employment_types: string[];
  applicable_gender:           string;
  minimum_service_period:      number;

  attachment_required:            boolean;
  medical_certificate_required:   boolean;
  medical_certificate_after_days: number;

  allow_negative_balance:     boolean;
  convert_to_lop:             boolean;
  allow_leave_cancellation:   boolean;
  cancellation_allowed_until: number;

  allow_probation_leave:     boolean;
  allow_notice_period_leave: boolean;
  allow_leave_extension:     boolean;
  allow_leave_combination:   boolean;
}

function defaultRules(): PolicyRuleFields {
  return {
    minimum_leave_duration: 0.5, maximum_leave_duration: 0, maximum_consecutive_days: 0, minimum_notice_period: 0,
    allow_half_day: true, allow_backdated_leave: false, maximum_backdated_days: 0,
    allow_future_leave: true, maximum_future_days: 0,
    sandwich_leave_enabled: false, count_holidays_as_leave: false, count_weekoffs_as_leave: false,
    applicable_branches: [], applicable_departments: [], applicable_designations: [],
    applicable_employment_types: [], applicable_gender: "all", minimum_service_period: 0,
    attachment_required: false, medical_certificate_required: false, medical_certificate_after_days: 3,
    allow_negative_balance: false, convert_to_lop: false,
    allow_leave_cancellation: true, cancellation_allowed_until: 0,
    allow_probation_leave: false, allow_notice_period_leave: false,
    allow_leave_extension: false, allow_leave_combination: false,
  };
}

function extractRules(p: LeavePolicy): PolicyRuleFields {
  return {
    minimum_leave_duration:   Number(p.minimum_leave_duration),
    maximum_leave_duration:   Number(p.maximum_leave_duration),
    maximum_consecutive_days: Number(p.maximum_consecutive_days),
    minimum_notice_period:    Number(p.minimum_notice_period),
    allow_half_day:           p.allow_half_day,
    allow_backdated_leave:    p.allow_backdated_leave,
    maximum_backdated_days:   Number(p.maximum_backdated_days),
    allow_future_leave:       p.allow_future_leave,
    maximum_future_days:      Number(p.maximum_future_days),
    sandwich_leave_enabled:   p.sandwich_leave_enabled,
    count_holidays_as_leave:  p.count_holidays_as_leave,
    count_weekoffs_as_leave:  p.count_weekoffs_as_leave,
    applicable_branches:         p.applicable_branches ?? [],
    applicable_departments:      p.applicable_departments ?? [],
    applicable_designations:     p.applicable_designations ?? [],
    applicable_employment_types: p.applicable_employment_types ?? [],
    applicable_gender:            p.applicable_gender || "all",
    minimum_service_period:      Number(p.minimum_service_period),
    attachment_required:            p.attachment_required,
    medical_certificate_required:   p.medical_certificate_required,
    medical_certificate_after_days: Number(p.medical_certificate_after_days),
    allow_negative_balance:     p.allow_negative_balance,
    convert_to_lop:             p.convert_to_lop,
    allow_leave_cancellation:   p.allow_leave_cancellation,
    cancellation_allowed_until: Number(p.cancellation_allowed_until),
    allow_probation_leave:     p.allow_probation_leave,
    allow_notice_period_leave: p.allow_notice_period_leave,
    allow_leave_extension:     p.allow_leave_extension,
    allow_leave_combination:   p.allow_leave_combination,
  };
}

// ── Small field-row helpers — shared with EligibilitySection ───────────────────

export function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "10px 0" }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{label}</span>
      <ToggleSwitch checked={checked} onChange={onChange} />
    </div>
  );
}

export function NumberRow({ label, value, onChange, suffix, step = 1 }: { label: string; value: number; onChange: (v: number) => void; suffix?: string; step?: number }) {
  return (
    <div className="field-group mb-16">
      <label className="field-label">{label}{suffix ? ` (${suffix})` : ""}</label>
      <input className="field-input" type="number" min={0} step={step} value={value} onChange={e => onChange(Number(e.target.value))} />
    </div>
  );
}

export function MultiCheckRow({ label, options, selected, onChange }: { label: string; options: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  function toggle(opt: string) {
    onChange(selected.includes(opt) ? selected.filter(o => o !== opt) : [...selected, opt]);
  }
  return (
    <div className="field-group mb-16" style={{ gridColumn: "1 / -1" }}>
      <label className="field-label">
        {label} <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>({selected.length === 0 ? "All" : `${selected.length} selected`})</span>
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, padding: "10px 12px", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", maxHeight: 140, overflowY: "auto" }}>
        {options.length === 0 ? (
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>No options available.</span>
        ) : options.map(opt => (
          <label key={opt} className="module-check">
            <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} />
            <span>{opt}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function Section({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className={`ti ${icon}`} /> {title}</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

export default function LeavePoliciesTab() {
  const { showToast } = useToast();
  const { data: policies, loading: loadingList, refetch } = useFetch<LeavePolicy[]>(API.leave.policy);
  const [selectedType, setSelectedType] = useState("");
  const [rules,  setRules]  = useState<PolicyRuleFields | null>(null);
  const [saving, setSaving] = useState(false);

  const list = policies ?? [];

  useEffect(() => {
    if (!selectedType && policies && policies.length > 0) {
      setSelectedType(policies[0].leave_type);
    }
  }, [policies, selectedType]);

  useEffect(() => {
    if (!selectedType) { setRules(null); return; }
    const policy = (policies ?? []).find(p => p.leave_type === selectedType);
    setRules(policy ? extractRules(policy) : defaultRules());
  }, [selectedType, policies]);

  function setField<K extends keyof PolicyRuleFields>(key: K, value: PolicyRuleFields[K]) {
    setRules(prev => prev ? { ...prev, [key]: value } : prev);
  }

  function discard() {
    const policy = list.find(p => p.leave_type === selectedType);
    setRules(policy ? extractRules(policy) : defaultRules());
  }

  async function save() {
    if (!rules || !selectedType) return;
    setSaving(true);
    try {
      const res = await clientApi.put<{ message: string }>(API.leave.policyDetail(selectedType), rules);
      showToast(res.data.message || "Policy updated.", "success");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to save leave policy.", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="scope-banner flex items-center gap-4 flex-wrap">
        <i className="ti ti-info-circle text-[22px] text-[var(--primary)] flex-shrink-0" />
        <div className="flex-1 min-w-[240px]">
          <div className="text-[13px] font-semibold text-[var(--on-bg)]">
            Configuring rules for one leave type at a time
          </div>
          <div className="text-xs text-[var(--on-variant)] mt-0.5">
            Every section below — Leave Application Rules, Holiday &amp; Week-off Rules, Eligibility Rules,
            Documentation Rules, Leave Restrictions, and Additional Rules — applies only to the leave type
            selected here, not to any other leave type.
          </div>
        </div>
        <div className="field-group min-w-[260px]">
          <label className="field-label">Leave Type</label>
          <select className="field-input" value={selectedType} onChange={e => setSelectedType(e.target.value)}>
            {list.map(t => (
              <option key={t.leave_type} value={t.leave_type}>{t.leave_type_display}</option>
            ))}
          </select>
        </div>
      </div>

      {loadingList || !rules ? (
        <div style={{ padding: "60px 24px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 22, animation: "spin 1s linear infinite" }} /> &nbsp;Loading policy…
        </div>
      ) : (
        <>
          <Section icon="ti-calendar-time" title="Leave Application Rules">
            <NumberRow label="Minimum Leave Duration" suffix="days" step={0.5} value={rules.minimum_leave_duration} onChange={v => setField("minimum_leave_duration", v)} />
            <NumberRow label="Maximum Leave Duration" suffix="0 = unlimited" value={rules.maximum_leave_duration} onChange={v => setField("maximum_leave_duration", v)} />
            <NumberRow label="Maximum Consecutive Days" suffix="0 = unlimited" value={rules.maximum_consecutive_days} onChange={v => setField("maximum_consecutive_days", v)} />
            <NumberRow label="Minimum Notice Period" suffix="days" value={rules.minimum_notice_period} onChange={v => setField("minimum_notice_period", v)} />
            <div style={{ gridColumn: "1 / -1" }}><ToggleRow label="Allow Half-Day Leave" checked={rules.allow_half_day} onChange={v => setField("allow_half_day", v)} /></div>
            <div style={{ gridColumn: "1 / -1" }}><ToggleRow label="Allow Backdated Leave" checked={rules.allow_backdated_leave} onChange={v => setField("allow_backdated_leave", v)} /></div>
            {rules.allow_backdated_leave && (
              <NumberRow label="Maximum Backdated Days" suffix="days" value={rules.maximum_backdated_days} onChange={v => setField("maximum_backdated_days", v)} />
            )}
            <div style={{ gridColumn: "1 / -1" }}><ToggleRow label="Allow Future Leave" checked={rules.allow_future_leave} onChange={v => setField("allow_future_leave", v)} /></div>
            {rules.allow_future_leave && (
              <NumberRow label="Maximum Future Days" suffix="0 = unlimited" value={rules.maximum_future_days} onChange={v => setField("maximum_future_days", v)} />
            )}
          </Section>

          <Section icon="ti-calendar-star" title="Holiday &amp; Week-off Rules">
            <ToggleRow label="Sandwich Leave Enabled" checked={rules.sandwich_leave_enabled} onChange={v => setField("sandwich_leave_enabled", v)} />
            <ToggleRow label="Count Holidays as Leave" checked={rules.count_holidays_as_leave} onChange={v => setField("count_holidays_as_leave", v)} />
            <ToggleRow label="Count Week-offs as Leave" checked={rules.count_weekoffs_as_leave} onChange={v => setField("count_weekoffs_as_leave", v)} />
          </Section>

          <EligibilitySection rules={rules} setField={setField} />

          <Section icon="ti-file-certificate" title="Documentation Rules">
            <ToggleRow label="Attachment Required" checked={rules.attachment_required} onChange={v => setField("attachment_required", v)} />
            <ToggleRow label="Medical Certificate Required" checked={rules.medical_certificate_required} onChange={v => setField("medical_certificate_required", v)} />
            {rules.medical_certificate_required && (
              <NumberRow label="Certificate Required After" suffix="days" value={rules.medical_certificate_after_days} onChange={v => setField("medical_certificate_after_days", v)} />
            )}
          </Section>

          <Section icon="ti-forbid-2" title="Leave Restrictions">
            <ToggleRow label="Allow Negative Balance" checked={rules.allow_negative_balance} onChange={v => setField("allow_negative_balance", v)} />
            <ToggleRow label="Convert Insufficient Balance to LOP" checked={rules.convert_to_lop} onChange={v => setField("convert_to_lop", v)} />
            <div style={{ gridColumn: "1 / -1" }}><ToggleRow label="Allow Leave Cancellation" checked={rules.allow_leave_cancellation} onChange={v => setField("allow_leave_cancellation", v)} /></div>
            {rules.allow_leave_cancellation && (
              <NumberRow label="Cancellation Allowed Until" suffix="days before start" value={rules.cancellation_allowed_until} onChange={v => setField("cancellation_allowed_until", v)} />
            )}
          </Section>

          <Section icon="ti-adjustments" title="Additional Rules">
            <ToggleRow label="Allow Leave During Probation" checked={rules.allow_probation_leave} onChange={v => setField("allow_probation_leave", v)} />
            <ToggleRow label="Allow Leave During Notice Period" checked={rules.allow_notice_period_leave} onChange={v => setField("allow_notice_period_leave", v)} />
            <ToggleRow label="Allow Leave Extension" checked={rules.allow_leave_extension} onChange={v => setField("allow_leave_extension", v)} />
            <ToggleRow label="Allow Combining Leave Types" checked={rules.allow_leave_combination} onChange={v => setField("allow_leave_combination", v)} />
          </Section>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 4 }}>
            <button className="btn btn-ghost" onClick={discard} disabled={saving}>Discard Changes</button>
            <button className="btn btn-filled" onClick={save} disabled={saving}>
              {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : "Save Policy"}
            </button>
          </div>
        </>
      )}
    </>
  );
}
