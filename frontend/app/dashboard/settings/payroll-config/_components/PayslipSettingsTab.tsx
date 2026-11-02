"use client";

// Payroll Configuration → Payslip: how payslips look. None of these settings
// change payroll amounts. The layout and the details printed are saved on
// each payslip when payroll is processed, so issued payslips keep their look.
// UAN / ESIC masking is applied by the server — a hidden or masked number
// never reaches the browser.

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollSettings, PayslipTemplate } from "@/types/payroll";

type Display = "hidden" | "masked" | "full";

const LAYOUTS: { value: PayslipTemplate; label: string; description: string }[] = [
  { value: "standard", label: "Standard", description: "Earnings and deductions in two columns with a net-pay banner." },
  { value: "wage_slip", label: "Wage slip", description: "Salary head / actual / earning / deduction grid with signatures and stamp." },
];

function displayOf(show: boolean, mask: boolean): Display {
  return !show ? "hidden" : mask ? "masked" : "full";
}

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

export default function PayslipSettingsTab({ settings, onSaved }: { settings: PayrollSettings; onSaved: () => void }) {
  const [template, setTemplate] = useState<PayslipTemplate>(settings.payslip_template ?? "standard");
  const [uan, setUan] = useState<Display>(displayOf(settings.show_uan, settings.mask_uan));
  const [esic, setEsic] = useState<Display>(displayOf(settings.show_esic, settings.mask_esic));
  const [rows, setRows] = useState((settings.fixed_deduction_rows ?? []).join("\n"));
  const [saving, setSaving] = useState(false);
  const [stampBusy, setStampBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      await clientApi.put(API.payroll.settings, {
        payslip_template: template,
        show_uan: uan !== "hidden", mask_uan: uan !== "full",
        show_esic: esic !== "hidden", mask_esic: esic !== "full",
        fixed_deduction_rows: rows.split("\n").map(r => r.trim()).filter(Boolean),
      });
      setMsg({ ok: true, text: "Payslip settings saved. They apply to payroll processed from now on." });
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: apiMessage(err, "Failed to save. Please try again.") });
    } finally {
      setSaving(false);
    }
  }

  async function uploadStamp(file: File | undefined) {
    if (!file) return;
    setStampBusy(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("stamp", file);
    try {
      await clientApi.post(API.payroll.settingsStamp, fd, { headers: { "Content-Type": undefined } });
      setMsg({ ok: true, text: "Stamp uploaded." });
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: apiMessage(err, "Could not upload the stamp.") });
    } finally {
      setStampBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function removeStamp() {
    setStampBusy(true);
    try {
      await clientApi.delete(API.payroll.settingsStamp);
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: apiMessage(err, "Could not remove the stamp.") });
    } finally {
      setStampBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-[var(--outline-v)]">
        <div className="font-semibold" style={{ color: "var(--on-bg)" }}>Payslip</div>
        <div className="text-[12px] mt-0.5" style={{ color: "var(--outline)" }}>
          Layout and details printed on payslips. Payroll amounts are not affected. A branch can use its own layout (Branch Config).
        </div>
      </div>

      <div className="p-5 flex flex-col gap-5">
        {msg && <div className={`alert ${msg.ok ? "alert-success" : "alert-error"}`}>{msg.text}</div>}

        <div>
          <div className="field-label mb-2">Layout</div>
          <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
            {LAYOUTS.map(l => (
              <label key={l.value} className="flex gap-3 items-start p-3 rounded-xl border cursor-pointer"
                style={{ borderColor: template === l.value ? "var(--primary)" : "var(--outline-v)", background: "var(--bg-low)" }}>
                <input type="radio" name="payslip-layout" checked={template === l.value} onChange={() => setTemplate(l.value)} />
                <span>
                  <span className="text-[13px] font-semibold" style={{ color: "var(--on-bg)" }}>{l.label}</span>
                  <span className="block text-[11px] mt-0.5" style={{ color: "var(--outline)" }}>{l.description}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          {([["UAN on payslip", uan, setUan, "********9012"], ["ESIC number on payslip", esic, setEsic, "******3210"]] as const)
            .map(([label, value, setter, example]) => (
              <div key={label}>
                <label className="field-label">{label}</label>
                <select className="field-input" value={value} onChange={e => setter(e.target.value as Display)}>
                  <option value="masked">Masked — last 4 digits ({example})</option>
                  <option value="full">Full number</option>
                  <option value="hidden">Hidden</option>
                </select>
              </div>
            ))}
        </div>

        {template === "wage_slip" && (
          <>
            <div>
              <label className="field-label">Always-shown deduction rows (wage slip)</label>
              <textarea className="field-input" rows={4} value={rows} onChange={e => setRows(e.target.value)}
                placeholder={"Food\nShoes\nAccommodation"} style={{ maxWidth: 360 }} />
              <div className="text-[11px] mt-1" style={{ color: "var(--outline)" }}>
                One label per line (up to 15). Shown as 0 when an employee has no such deduction that month.
              </div>
            </div>

            <div>
              <div className="field-label mb-2">Stamp / authorised signature</div>
              <div className="flex flex-wrap items-center gap-3">
                {settings.payslip_stamp_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={settings.payslip_stamp_url} alt="Payslip stamp"
                    style={{ maxHeight: 72, maxWidth: 140, objectFit: "contain", border: "1px solid var(--outline-v)", borderRadius: 8 }} />
                )}
                <label className="btn btn-ghost btn-sm" style={{ cursor: stampBusy ? "default" : "pointer" }}>
                  <i className="ti ti-upload" /> {settings.payslip_stamp_url ? "Replace" : "Upload"} image
                  <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={stampBusy}
                    onChange={e => uploadStamp(e.target.files?.[0])} />
                </label>
                {settings.payslip_stamp_url && (
                  <button className="btn btn-ghost btn-sm" onClick={removeStamp} disabled={stampBusy}>
                    <i className="ti ti-trash" /> Remove
                  </button>
                )}
                <span className="text-[11px]" style={{ color: "var(--outline)" }}>PNG, JPEG or WebP, under 2 MB.</span>
              </div>
            </div>
          </>
        )}

        <div className="flex justify-end">
          <button className="btn btn-filled" onClick={save} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 animate-spin text-sm" /> Saving…</> : <><i className="ti ti-device-floppy text-sm" /> Save</>}
          </button>
        </div>
      </div>
    </div>
  );
}
