"use client";

import { useState } from "react";
import PayrollPeriodStep      from "./PayrollPeriodStep";
import EarningsDeductionsStep from "./EarningsDeductionsStep";
import ReimbBonusesStep       from "./ReimbBonusesStep";
import CalculationStep        from "./CalculationStep";
import ValidationStep         from "./ValidationStep";
import ApprovalStep           from "./ApprovalStep";
import PayslipsStep           from "./PayslipsStep";
import BankTransferStep       from "./BankTransferStep";

interface Props { onCancel: () => void; }

const STEPS = [
  { label: "Period Setup",      icon: "ti-calendar"       },
  { label: "Earn. & Deduct.",   icon: "ti-cash"           },
  { label: "Reimb. & Bonuses",  icon: "ti-gift"           },
  { label: "Calculation",       icon: "ti-calculator"     },
  { label: "Validation",        icon: "ti-shield-check"   },
  { label: "Approval",          icon: "ti-user-check"     },
  { label: "Payslips",          icon: "ti-file-invoice"   },
  { label: "Bank Transfer",     icon: "ti-credit-card"    },
];

export default function RunPayrollWizard({ onCancel }: Props) {
  const [step, setStep] = useState(0);
  const next = () => setStep(s => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep(s => Math.max(s - 1, 0));

  return (
    <div>
      {/* Step bar */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
              Step {step + 1} of {STEPS.length} — {STEPS[step].label}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={onCancel}>
              <i className="ti ti-x" /> Cancel
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", marginTop: 14, overflowX: "auto", paddingBottom: 4 }}>
            {STEPS.map((s, idx) => (
              <div key={idx} style={{ display: "flex", alignItems: "center", flex: idx < STEPS.length - 1 ? 1 : "none", minWidth: 0 }}>
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

      {step === 0 && <PayrollPeriodStep      onNext={next} onBack={onCancel} />}
      {step === 1 && <EarningsDeductionsStep onNext={next} onBack={back}    />}
      {step === 2 && <ReimbBonusesStep       onNext={next} onBack={back}    />}
      {step === 3 && <CalculationStep        onNext={next} onBack={back}    />}
      {step === 4 && <ValidationStep         onNext={next} onBack={back}    />}
      {step === 5 && <ApprovalStep           onNext={next} onBack={back}    />}
      {step === 6 && <PayslipsStep           onNext={next} onBack={back}    />}
      {step === 7 && <BankTransferStep       onNext={onCancel} onBack={back} />}
    </div>
  );
}
