"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { MONTH_NAMES } from "@/lib/fiscalYear";
import type { FinancialYearConfig, MonthName } from "@/types/company";

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function FinancialYearSection() {
  const user = useCurrentUser();
  // The API enforces this server-side too (403 on PUT for anyone else) —
  // this only controls whether the edit form renders at all.
  const isSystemAdmin = user?.is_superuser === true;

  const { data, loading, error: loadError, refetch } = useFetch<FinancialYearConfig>(API.settings.financialYear);

  const [draftMonth, setDraftMonth] = useState<MonthName>("January");
  const [touched,     setTouched]     = useState(false);
  const [saving,      setSaving]      = useState(false);
  const [saveError,   setSaveError]   = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Seed the draft from the loaded config — but stop the moment the admin
  // has picked something themselves, so a background refetch never clobbers
  // an in-progress edit.
  useEffect(() => {
    if (data && !touched) setDraftMonth(data.financial_year_start_month);
  }, [data, touched]);

  const dirty = !!data && draftMonth !== data.financial_year_start_month;

  async function save() {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      await clientApi.put(API.settings.financialYear, { financial_year_start_month: draftMonth });
      setTouched(false);
      setSaveSuccess(true);
      refetch();
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      setSaveError(e.message ?? "Failed to update financial year configuration.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-time" /> Financial Year Configuration</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 18, lineHeight: 1.6 }}>
          Configure the financial year once, here. Leave Allocation, Carry Forward, Attendance, Payroll,
          and Reports all derive their current / previous / next year from this single setting instead of
          each assuming a January–December calendar year.
        </p>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--on-variant)", fontSize: 13 }}>
            <Spin /> Loading financial year configuration…
          </div>
        )}

        {!loading && loadError && (
          <div className="alert alert-error">
            <i className="ti ti-alert-circle" />
            <div>{loadError}</div>
          </div>
        )}

        {!loading && !loadError && data && (
          <>
            {saveError && (
              <div className="alert alert-error mb-16">
                <i className="ti ti-alert-circle" />
                <div>{saveError}</div>
              </div>
            )}
            {saveSuccess && (
              <div className="alert alert-success mb-16">
                <i className="ti ti-circle-check" />
                <div>Financial year configuration updated.</div>
              </div>
            )}

            <div className="form-row cols-2" style={{ marginBottom: 20 }}>
              <div className="field-group" style={{ marginBottom: 0 }}>
                <label className="field-label">Financial Year Starts In</label>
                {isSystemAdmin ? (
                  <select
                    className="field-input"
                    value={draftMonth}
                    onChange={e => { setTouched(true); setSaveSuccess(false); setDraftMonth(e.target.value as MonthName); }}
                  >
                    {MONTH_NAMES.map(name => <option key={name} value={name}>{name}</option>)}
                  </select>
                ) : (
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)" }}>{data.financial_year_start_month}</div>
                )}
              </div>
            </div>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: isSystemAdmin ? 18 : 0 }}>
              {[
                { label: "Previous Year", value: data.previous_financial_year, active: false },
                { label: "Current Year",  value: data.current_financial_year, active: true  },
                { label: "Next Year",     value: data.next_financial_year,     active: false },
              ].map(({ label, value, active }) => (
                <div
                  key={label}
                  style={{
                    padding: "10px 16px", borderRadius: 8, minWidth: 130,
                    border: `1.5px solid ${active ? "var(--primary)" : "var(--outline-v)"}`,
                    background: active ? "rgba(30,78,140,0.05)" : "transparent",
                  }}
                >
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 3 }}>{label}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>{value}</div>
                </div>
              ))}
            </div>

            {isSystemAdmin && (
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <button className="btn btn-filled btn-sm" onClick={save} disabled={!dirty || saving}>
                  {saving ? <><Spin /> Saving…</> : <><i className="ti ti-device-floppy" /> Save</>}
                </button>
                {!dirty && !saveSuccess && (
                  <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Pick a different month to change it.</span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
