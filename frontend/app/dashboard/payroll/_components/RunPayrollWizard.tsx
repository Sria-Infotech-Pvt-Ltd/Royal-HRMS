"use client";

import { useState, useEffect, useRef } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollSettings } from "@/types/payroll";
import PayrollPeriodStep      from "./PayrollPeriodStep";
import ApprovalStep           from "./ApprovalStep";
import EarningsDeductionsStep from "./EarningsDeductionsStep";
import ReimbBonusesStep       from "./ReimbBonusesStep";
import CalculationStep        from "./CalculationStep";
import ValidationStep         from "./ValidationStep";
import PayslipsStep           from "./PayslipsStep";
import BankTransferStep       from "./BankTransferStep";

// Maps a cycle's backend status to the wizard step key to resume at
const STATUS_STEP_KEY: Record<string, string> = {
  draft:               "approval",
  attendance_pending:  "approval",
  attendance_approved: "earnings",
  processing:          "calc",
  payslips_generated:  "validation",
  query_window_open:   "payslips",
  paid:                "paid",
};

interface Props {
  onCancel: () => void;
  initialCycleId?: string;
  initialStatus?: string;
}

interface StepDef { key: string; label: string; icon: string; }

export default function RunPayrollWizard({ onCancel, initialCycleId, initialStatus }: Props) {
  const { data: settings } = useFetch<PayrollSettings>(API.payroll.settings);
  const [step,    setStep]    = useState(0);
  const [cycleId, setCycleId] = useState<string | null>(initialCycleId ?? null);
  const jumped = useRef(false);

  const showReimb = !!(settings?.enable_reimbursements || settings?.enable_bonuses);

  const STEPS: StepDef[] = [
    { key: "period",     label: "Period Setup",    icon: "ti-calendar"      },
    { key: "approval",   label: "Approval",        icon: "ti-user-check"    },
    { key: "earnings",   label: "Earn. & Deduct.", icon: "ti-cash"          },
    ...(showReimb ? [{ key: "reimb", label: "Reimb. & Bonuses", icon: "ti-gift" }] : []),
    { key: "calc",       label: "Calculation",     icon: "ti-calculator"    },
    { key: "validation", label: "Validation",      icon: "ti-shield-check"  },
    { key: "payslips",   label: "Payslips",        icon: "ti-file-invoice"  },
    { key: "paid",       label: "Mark as Paid",    icon: "ti-circle-check"  },
  ];

  // Once settings load and STEPS is final, jump to the correct step for a resumed cycle
  useEffect(() => {
    if (jumped.current || !initialStatus || !settings) return;
    const targetKey = STATUS_STEP_KEY[initialStatus];
    if (!targetKey) return;
    const idx = STEPS.findIndex(s => s.key === targetKey);
    if (idx >= 0) setStep(idx);
    jumped.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const currentKey = STEPS[step]?.key ?? "";
  const next = () => setStep(s => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep(s => Math.max(s - 1, 0));

  function handleCycleCreated(id: string) {
    setCycleId(id);
    next();
  }

  return (
    <div>
      {/* Step progress bar */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
              Step {step + 1} of {STEPS.length} — {STEPS[step]?.label}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={onCancel}>
              <i className="ti ti-x" /> Cancel
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", marginTop: 14, overflowX: "auto", paddingBottom: 4 }}>
            {STEPS.map((s, idx) => (
              <div key={s.key} style={{ display: "flex", alignItems: "center", flex: idx < STEPS.length - 1 ? 1 : "none", minWidth: 0 }}>
                <div
                  style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, cursor: idx <= step ? "pointer" : "default" }}
                  onClick={() => idx <= step && setStep(idx)}
                >
                  <div style={{
                    width: 34, height: 34, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 13, fontWeight: 600, flexShrink: 0,
                    background: idx < step ? "var(--success)" : idx === step ? "var(--primary)" : "var(--bg-high)",
                    color: idx <= step ? "#fff" : "var(--on-variant)",
                    boxShadow: idx === step ? "0 0 0 3px rgba(30,78,140,0.2)" : "none",
                    transition: "all 0.2s",
                  }}>
                    {idx < step
                      ? <i className="ti ti-check" style={{ fontSize: 14 }} />
                      : <i className={`ti ${s.icon}`} style={{ fontSize: 13 }} />}
                  </div>
                  <span style={{
                    fontSize: 10, whiteSpace: "nowrap", fontWeight: idx === step ? 600 : 400,
                    color: idx === step ? "var(--primary)" : idx < step ? "var(--success)" : "var(--outline)",
                  }}>
                    {s.label}
                  </span>
                </div>
                {idx < STEPS.length - 1 && (
                  <div style={{
                    flex: 1, height: 2, marginBottom: 18, marginLeft: 6, marginRight: 6,
                    background: idx < step ? "var(--success)" : "var(--bg-high)",
                    borderRadius: 99, transition: "background 0.3s",
                  }} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Step content */}
      {currentKey === "period" && (
        <PayrollPeriodStep settings={settings} onNext={handleCycleCreated} onBack={onCancel} />
      )}
      {currentKey === "approval" && cycleId && (
        <ApprovalStep cycleId={cycleId} settings={settings} onNext={next} onBack={back} />
      )}
      {currentKey === "earnings" && cycleId && (
        <EarningsDeductionsStep cycleId={cycleId} onNext={next} onBack={back} />
      )}
      {currentKey === "reimb" && cycleId && settings && (
        <ReimbBonusesStep
          cycleId={cycleId}
          enableReimbursements={settings.enable_reimbursements}
          enableBonuses={settings.enable_bonuses}
          onNext={next}
          onBack={back}
        />
      )}
      {currentKey === "calc" && cycleId && (
        <CalculationStep cycleId={cycleId} onNext={next} onBack={back} />
      )}
      {currentKey === "validation" && cycleId && (
        <ValidationStep cycleId={cycleId} onNext={next} onBack={back} />
      )}
      {currentKey === "payslips" && cycleId && (
        <PayslipsStep cycleId={cycleId} onNext={next} onBack={back} />
      )}
      {currentKey === "paid" && cycleId && (
        <BankTransferStep cycleId={cycleId} onNext={onCancel} onBack={back} />
      )}
    </div>
  );
}
