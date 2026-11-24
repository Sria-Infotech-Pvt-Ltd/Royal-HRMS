"use client";

// ─────────────────────────────────────────────────────────────────────────
// "Edit record" — pixel-faithful mock build (mock/placeholder data only).
//
// This is a STANDALONE demo component, deliberately separate from the
// real, backend-wired `EditRecordModal.tsx` already used by the Employee
// Directory's "Edit full record" button. It exists to match a detailed
// visual/field spec exactly, with one hardcoded demo employee and local
// React state only — nothing here reads or writes any API. See the
// assumptions list at the bottom of this file for every [TO CONFIRM] call
// made while building it.
//
// Self-contained: all sub-components, mock data and Tailwind classes live
// in this one file, per the spec's own "single self-contained component"
// instruction.
// ─────────────────────────────────────────────────────────────────────────

import { useMemo, useState, type ReactNode } from "react";
import { useT } from "@/hooks/useI18n";
import { confirmDialog } from "@/components/DialogProvider";

const PURPLE = "#6D28D9";

// ───────────────────────── Mock data types & seed ─────────────────────────

interface EmergencyContact {
  id: string; name: string; relationship: string; phone: string;
  altPhone: string; email: string; address: string; isPrimary: boolean;
}
interface FamilyMember {
  id: string; name: string; relationship: string; dob: string;
  gender: string; bloodGroup: string; isDependent: "yes" | "no";
}
interface Nominee {
  id: string; familyMemberId: string; scheme: string; sharePercent: string;
}
interface Qualification {
  id: string; level: string; institution: string; specialization: string;
  gradeOrPercentage: string; startDate: string; endDate: string; isHighest: boolean;
}
interface Experience {
  id: string; employer: string; designation: string; employmentType: string;
  startDate: string; lastWorkingDay: string; reason: string;
}
interface Asset {
  id: string; assetType: string; tagNumber: string; condition: string;
}

interface DemoRecord {
  // Personal identity
  fullName: string; photoUrl: string; dateOfBirth: string;
  personalEmail: string; personalPhone: string;
  emergencyContacts: EmergencyContact[];
  // Employment
  dateOfJoining: string; workEmail: string; employmentType: string;
  probationMonths: string; noticeDays: string;
  position: string; reportingManager: string; dottedLineManager: string;
  workLocation: string; workMode: string; shift: string; weeklyOff: string[];
  attendanceScheme: string; leavePlan: string;
  salaryStructure: string; annualCtc: string;
  // Basic pay
  payScaleGroup: string; payScaleLevel: string; basicPctOfCtc: string;
  taxRegime: string;
  // Statutory & accounts
  pan: string; aadhaar: string; nameAsPerPan: string;
  passportNumber: string; passportExpiry: string; residentialStatus: string;
  pfCovered: "yes" | "no"; uan: string; pfNumber: string; nameOnPf: string; pfContribution: string;
  esiCovered: "yes" | "no"; lwfApplicable: "yes" | "no";
  accountHolderName: string; accountNumber: string; confirmAccountNumber: string; ifscCode: string;
  // Family & nomination
  familyMembers: FamilyMember[]; nominees: Nominee[];
  guardianName: string; guardianRelationship: string; guardianAddress: string;
  // Education & experience
  qualifications: Qualification[]; experiences: Experience[];
  coreSkills: string; certifications: string;
  // Documents
  verificationStatus: string; verificationCompletedOn: string; verificationProvider: string;
  // Assets
  assets: Asset[]; cardNumber: string; cardValidFrom: string; cardValidTill: string;
}

let uid = 0;
const nextId = () => `demo-${++uid}`;

function seedDemoRecord(): DemoRecord {
  return {
    fullName: "Meera Iyer", photoUrl: "", dateOfBirth: "1986-08-14",
    personalEmail: "meera.iyer.demo@example.com", personalPhone: "+91 90000 10011",
    emergencyContacts: [
      { id: nextId(), name: "Demo Contact 11", relationship: "Sibling", phone: "+91 91111 20011", altPhone: "", email: "", address: "", isPrimary: true },
    ],
    dateOfJoining: "2017-04-01", workEmail: "", employmentType: "Permanent",
    probationMonths: "6", noticeDays: "60",
    position: "VP, Engineering", reportingManager: "CEO Office", dottedLineManager: "",
    workLocation: "Gachibowli", workMode: "Office", shift: "General 09:30–18:30", weeklyOff: ["Saturday", "Sunday"],
    attendanceScheme: "Standard – Office", leavePlan: "Standard India Leave Policy",
    salaryStructure: "Standard India CTC", annualCtc: "3420000",
    payScaleGroup: "L2", payScaleLevel: "Associate", basicPctOfCtc: "40",
    taxRegime: "New regime (115BAC)",
    pan: "ABCDE1234F", aadhaar: "123456784821", nameAsPerPan: "",
    passportNumber: "", passportExpiry: "", residentialStatus: "Resident",
    pfCovered: "yes", uan: "", pfNumber: "", nameOnPf: "", pfContribution: "EPF + EPS",
    esiCovered: "no", lwfApplicable: "no",
    accountHolderName: "Meera Iyer", accountNumber: "500100227734", confirmAccountNumber: "500100227734", ifscCode: "HDFC0001234",
    familyMembers: [
      { id: nextId(), name: "Arvind Iyer", relationship: "Spouse", dob: "1984-02-10", gender: "Male", bloodGroup: "O+", isDependent: "yes" },
    ],
    nominees: [],
    guardianName: "", guardianRelationship: "", guardianAddress: "",
    qualifications: [
      { id: nextId(), level: "Master's", institution: "IIT Bombay", specialization: "Computer Science", gradeOrPercentage: "8.7 CGPA", startDate: "2007-07-01", endDate: "2009-05-31", isHighest: true },
    ],
    experiences: [
      { id: nextId(), employer: "Previous Co Pvt Ltd", designation: "Engineering Manager", employmentType: "Full-time", startDate: "2013-06-01", lastWorkingDay: "2017-03-24", reason: "Career growth" },
    ],
    coreSkills: "Distributed systems, engineering leadership, platform architecture",
    certifications: "AWS Solutions Architect, 2021",
    verificationStatus: "Verified", verificationCompletedOn: "2017-03-20", verificationProvider: "Demo BGV Partner / REF-11234",
    assets: [
      { id: nextId(), assetType: "Laptop", tagNumber: "AST-00119", condition: "New" },
    ],
    cardNumber: "", cardValidFrom: "2017-04-01", cardValidTill: "",
  };
}

// ───────────────────────── Primitives ─────────────────────────

function Pill({ children, tone = "grey" }: { children: ReactNode; tone?: "grey" | "red" | "amber" | "green" | "purple" | "blue" }) {
  const tones: Record<string, string> = {
    grey: "bg-slate-100 text-slate-500",
    red: "bg-red-100 text-red-600",
    amber: "bg-amber-100 text-amber-700",
    green: "bg-emerald-100 text-emerald-700",
    purple: "bg-violet-100 text-violet-700",
    blue: "bg-sky-100 text-sky-700",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[9.5px] font-bold tracking-wide uppercase ${tones[tone]}`}>
      {children}
    </span>
  );
}

function SuggestButton({ onClick }: { onClick: () => void }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onClick}
      className="ml-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold"
      style={{ borderColor: PURPLE, color: PURPLE }}
    >
      {t("✦ Suggest")}
    </button>
  );
}

function Label({ children, required, tag, onSuggest }: { children: ReactNode; required?: boolean; tag?: string; onSuggest?: () => void }) {
  const t = useT();
  return (
    <label className="flex items-center flex-wrap gap-1 text-[12.5px] font-medium text-slate-700 mb-1">
      {children}
      {required && <span className="text-red-500">*</span>}
      {tag && <Pill>{t(tag)}</Pill>}
      {onSuggest && <SuggestButton onClick={onSuggest} />}
    </label>
  );
}

function Helper({ children, tone = "grey" }: { children: ReactNode; tone?: "grey" | "red" | "green" }) {
  const cls = tone === "red" ? "text-red-500" : tone === "green" ? "text-emerald-600" : "text-slate-400";
  return <div className={`text-[11px] mt-1 ${cls}`}>{children}</div>;
}

const inputBase =
  "w-full h-11 rounded-lg border border-slate-200 px-3 text-[13px] text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2";

function TextInput(props: { value: string; onChange: (v: string) => void; placeholder?: string; readOnly?: boolean; type?: string }) {
  const t = useT();
  return (
    <input
      type={props.type ?? "text"}
      value={props.value}
      onChange={e => props.onChange(e.target.value)}
      placeholder={props.placeholder ? t(props.placeholder) : undefined}
      readOnly={props.readOnly}
      className={`${inputBase} ${props.readOnly ? "bg-slate-50 text-slate-500" : "bg-white"}`}
      style={{ outlineColor: PURPLE }}
    />
  );
}

function DateInput(props: { value: string; onChange: (v: string) => void; readOnly?: boolean; disabled?: boolean }) {
  return (
    <input
      type="date"
      value={props.value}
      onChange={e => props.onChange(e.target.value)}
      readOnly={props.readOnly}
      disabled={props.disabled}
      className={`${inputBase} ${props.readOnly || props.disabled ? "bg-slate-50 text-slate-500" : "bg-white"}`}
    />
  );
}

function Select(props: { value: string; onChange: (v: string) => void; options: string[]; placeholder?: string; readOnly?: boolean }) {
  const t = useT();
  if (props.readOnly) {
    return <div className={`${inputBase} bg-slate-50 text-slate-500 flex items-center`}>{props.value ? t(props.value) : "—"}</div>;
  }
  return (
    <select
      value={props.value}
      onChange={e => props.onChange(e.target.value)}
      className={`${inputBase} bg-white appearance-none`}
    >
      <option value="">{t(props.placeholder ?? "Select")}</option>
      {props.options.map(o => <option key={o} value={o}>{t(o)}</option>)}
    </select>
  );
}

function Toggle({ value, onChange }: { value: "yes" | "no"; onChange: (v: "yes" | "no") => void }) {
  const t = useT();
  return (
    <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
      {(["yes", "no"] as const).map(v => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className="px-4 py-1.5 text-[12.5px] font-semibold"
          style={value === v ? { background: PURPLE, color: "#fff" } : { background: "#fff", color: "#475569" }}
        >
          {v === "yes" ? t("Yes") : t("No")}
        </button>
      ))}
    </div>
  );
}

function RevealField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const t = useT();
  const [revealed, setRevealed] = useState(false);
  const masked = value ? value.replace(/./g, "•").slice(0, Math.max(0, value.length - 4)) + value.slice(-4) : "";
  return (
    <div className="relative">
      <input
        type="text"
        value={revealed ? value : masked}
        onChange={e => onChange(e.target.value)}
        readOnly={!revealed}
        placeholder={placeholder ? t(placeholder) : undefined}
        className={`${inputBase} pr-9 ${revealed ? "bg-white" : "bg-slate-50 text-slate-500"}`}
      />
      <button
        type="button"
        onClick={() => setRevealed(r => !r)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
        title={revealed ? t("Hide — this reveal is audit-logged") : t("Reveal — logged to the audit trail")}
      >
        <i className={`ti ${revealed ? "ti-eye-off" : "ti-eye"}`} />
      </button>
    </div>
  );
}

function AttachButton({ label }: { label: string }) {
  const t = useT();
  return (
    <button type="button" className="mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-dashed border-slate-300 text-[11px] text-slate-500">
      <i className="ti ti-paperclip text-[12px]" /> {t(label)}
    </button>
  );
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full py-2.5 rounded-lg text-[13px] font-semibold border border-dashed"
      style={{ color: PURPLE, borderColor: "#ddd6fe", background: "#faf7ff" }}
    >
      + {t(label)}
    </button>
  );
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  const t = useT();
  return (
    <button type="button" onClick={onClick} className="px-2.5 py-1 rounded-md border border-red-200 text-red-600 text-[11px] font-semibold">
      {t("Remove")}
    </button>
  );
}

function RepeatCard({ label, onRemove, extra, children }: { label: string; onRemove: () => void; extra?: ReactNode; children: ReactNode }) {
  const t = useT();
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 mb-3">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-bold tracking-wide uppercase text-slate-400">{t(label)}</span>
          {extra}
        </div>
        <RemoveButton onClick={onRemove} />
      </div>
      {children}
    </div>
  );
}

function SubHead({ children }: { children: ReactNode }) {
  return (
    <div className="pt-5 mt-5 border-t border-slate-100 first:border-0 first:pt-0 first:mt-0">
      <div className="text-[10.5px] font-bold tracking-wider uppercase text-slate-400 mb-3">{children}</div>
    </div>
  );
}

function Grid3({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 md:grid-cols-3 gap-x-5 gap-y-4">{children}</div>;
}

function SectionTitle({ a, b, sub }: { a: string; b: string; sub: string }) {
  const t = useT();
  return (
    <div className="sticky top-0 bg-white/95 backdrop-blur z-10 pb-3 pt-1 border-b border-slate-100 mb-5">
      <h2 className="text-[19px] font-bold text-slate-800">
        {t(a)} <em className="italic" style={{ color: PURPLE }}>{t(b)}</em>
      </h2>
      <p className="text-[12px] text-slate-400 mt-0.5">{t(sub)}</p>
    </div>
  );
}

// ───────────────────────── Nav config ─────────────────────────

const RELATIONSHIPS = ["Father", "Mother", "Spouse", "Child", "Sibling", "Friend", "Parent"];
const SCHEMES = ["EPF + EPS", "Gratuity", "Both"];

interface NavItem { label: string; sub: string; tag?: { text: string; tone: "red" | "amber" | "green" }; group?: string }
const NAV: NavItem[] = [
  { label: "Personal identity", sub: "Name, photo, DOB, contact" },
  { label: "Employment", sub: "Role, reporting, work setup" },
  { label: "Basic pay", sub: "Wage types and pay scale" },
  { label: "Statutory & accounts", sub: "PAN, PF, ESI, bank", tag: { text: "Sensitive", tone: "red" } },
  { label: "Family & nomination", sub: "Dependants and nominees", group: "Records & compliance", tag: { text: "EPFO", tone: "amber" } },
  { label: "Education & experience", sub: "Qualifications, past employers" },
  { label: "Documents", sub: "Joining paperwork" },
  { label: "Assets", sub: "Laptop, phone, access card", tag: { text: "New", tone: "green" } },
];

// ───────────────────────── Main component ─────────────────────────

export default function EditRecordModalMock({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [r, setR] = useState<DemoRecord>(() => seedDemoRecord());
  const [step, setStep] = useState(0);
  const [dirty, setDirty] = useState(false);

  function patch(partial: Partial<DemoRecord>) {
    setR(prev => ({ ...prev, ...partial }));
    setDirty(true);
  }

  // ── Basic pay derivation (live from Annual fixed CTC) ──
  const pay = useMemo(() => {
    const ctc = Number(r.annualCtc) || 0;
    const monthlyCtc = ctc / 12;
    const basicPct = Number(r.basicPctOfCtc) / 100 || 0.4;
    const basic = monthlyCtc * basicPct;
    const da = 0; // counts as wages with Basic — no separate DA configured in this demo
    const basicPlusDa = basic + da;
    const isMetro = false;
    const hra = basicPlusDa * (isMetro ? 0.5 : 0.4);
    const conveyance = 0;
    const medical = 0;
    const lta = basicPlusDa * 0.0833;

    const employerPfBase = Math.min(basicPlusDa, 15000);
    const employerPf = employerPfBase * 0.0367;
    const employerEps = employerPfBase * 0.0833;
    const gratuity = basicPlusDa * 0.0481;
    const grossSoFar = basic + da + hra + conveyance + medical + lta;
    const employerEsi = 0; // esi not applicable above the wage threshold in this demo
    const employerContributions = employerPf + employerEps + gratuity + employerEsi;

    const specialAllowance = Math.max(0, monthlyCtc - grossSoFar - employerContributions);
    const monthlyGross = grossSoFar + specialAllowance;

    const employeePf = Math.min(basicPlusDa, 15000) * 0.12;
    const employeeEsi = 0;
    const professionalTax = 200; // flat demo PT slab for the work-location state
    const statutoryDeductions = employeePf + employeeEsi + professionalTax;

    const costToCompany = monthlyGross + employerContributions;
    const netTakeHome = monthlyGross - statutoryDeductions;

    return {
      basic, da, hra, conveyance, medical, lta, specialAllowance,
      employerPf, employerEps, gratuity, employerEsi,
      employeePf, employeeEsi, professionalTax,
      monthlyGross, employerContributions, costToCompany, annualCostToCompany: costToCompany * 12,
      statutoryDeductions, netTakeHome,
    };
  }, [r.annualCtc, r.basicPctOfCtc]);

  const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

  // ── Required-field completeness (drives the status card) ──
  const missing = useMemo(() => {
    const items: string[] = [];
    if (!r.dateOfJoining) items.push("Employment: Date of joining");
    if (!r.employmentType) items.push("Employment: Employment type");
    if (!r.position) items.push("Employment: Position");
    if (!r.reportingManager) items.push("Employment: Reporting manager");
    if (!r.workLocation) items.push("Employment: Work location");
    if (!r.attendanceScheme) items.push("Employment: Attendance scheme");
    if (!r.leavePlan) items.push("Employment: Leave plan");
    if (!r.pan) items.push("Statutory: PAN");
    if (!r.aadhaar) items.push("Statutory: Aadhaar");
    if (!r.accountHolderName) items.push("Statutory: Account holder name");
    if (!r.accountNumber) items.push("Statutory: Account number");
    if (r.accountNumber !== r.confirmAccountNumber) items.push("Statutory: Account numbers don't match");
    if (!r.ifscCode) items.push("Statutory: IFSC code");
    return items;
  }, [r]);

  const schemeShareTotals = SCHEMES.filter(s => s !== "Both").map(scheme => ({
    scheme,
    total: r.nominees.filter(n => n.scheme === scheme || n.scheme === "Both").reduce((sum, n) => sum + (Number(n.sharePercent) || 0), 0),
  }));

  function familyName(id: string) {
    const f = r.familyMembers.find(m => m.id === id);
    return f ? `${f.name} (${f.relationship})` : "";
  }
  function familyRelationship(id: string) {
    return r.familyMembers.find(m => m.id === id)?.relationship ?? "";
  }

  const totalExperienceLabel = useMemo(() => {
    if (r.experiences.length === 0) return "0 mo";
    // Simple non-overlap-aware sum for demo purposes.
    let totalDays = 0;
    for (const e of r.experiences) {
      if (!e.startDate) continue;
      const end = e.lastWorkingDay ? new Date(e.lastWorkingDay) : new Date(r.dateOfJoining);
      const start = new Date(e.startDate);
      totalDays += Math.max(0, (end.getTime() - start.getTime()) / 86400000);
    }
    const months = Math.round(totalDays / 30.44);
    return months < 12 ? `${months} mo` : `${Math.floor(months / 12)} yr ${months % 12} mo`;
  }, [r.experiences, r.dateOfJoining]);

  async function handleClose() {
    if (dirty && !(await confirmDialog(t("Discard unsaved changes?")))) return;
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-[1120px] max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h1 className="text-[20px] font-bold text-slate-800">
              {t("Edit")} <em className="italic" style={{ color: PURPLE }}>{t("record")}</em>
            </h1>
            <p className="text-[12.5px] text-slate-400 mt-1 max-w-[56ch]">
              {t("Jump to any section, change what you need, and save. Nothing else has to be re-entered.")}
            </p>
          </div>
          <button onClick={handleClose} className="text-slate-400 hover:text-slate-600 text-[20px] leading-none">×</button>
        </div>

        {/* Body: nav + content */}
        <div className="flex flex-1 min-h-0">
          {/* Left navigator */}
          <div className="w-[280px] shrink-0 border-r border-slate-100 bg-slate-50/50 p-3 overflow-y-auto">
            {NAV.map((item, i) => (
              <div key={item.label}>
                {item.group && (
                  <div className="text-[9.5px] font-bold tracking-widest uppercase text-slate-400 px-2 pt-4 pb-1.5">{t(item.group)}</div>
                )}
                <button
                  onClick={() => setStep(i)}
                  className="w-full text-left rounded-lg px-3 py-2.5 mb-0.5 transition-colors"
                  style={i === step ? { background: "#f3e8ff" } : undefined}
                >
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[12.5px] font-semibold" style={{ color: i === step ? PURPLE : "#334155" }}>{t(item.label)}</span>
                    {item.tag && <Pill tone={item.tag.tone}>{t(item.tag.text)}</Pill>}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{t(item.sub)}</div>
                </button>
              </div>
            ))}

            <div
              className="mt-4 rounded-lg p-3 text-[11.5px]"
              style={missing.length === 0 ? { background: "#ecfdf5", color: "#065f46" } : { background: "#fff7ed", color: "#9a3412" }}
            >
              <div className="font-bold mb-1">{missing.length === 0 ? t("Nothing outstanding") : (missing.length === 1 ? t("{count} item needs attention", { count: missing.length }) : t("{count} items need attention", { count: missing.length }))}</div>
              {missing.length === 0 ? (
                <div>{t("All required fields are complete. Optional sections can be finished after joining.")}</div>
              ) : (
                <ul className="list-disc list-inside space-y-0.5">
                  {missing.slice(0, 5).map(m => <li key={m}>{t(m)}</li>)}
                  {missing.length > 5 && <li>{t("+{count} more", { count: missing.length - 5 })}</li>}
                </ul>
              )}
            </div>
          </div>

          {/* Right content pane */}
          <div className="flex-1 overflow-y-auto px-7 py-5">
            {/* 1. Personal identity */}
            {step === 0 && (
              <>
                <SectionTitle a="Personal" b="identity" sub="Name, photo, date of birth and a few basics." />
                <Grid3>
                  <div><Label required>{t("Full legal name")}</Label><TextInput value={r.fullName} onChange={v => patch({ fullName: v })} placeholder={t("Full name")} /></div>
                  <div><Label required>{t("Date of birth")}</Label><DateInput value={r.dateOfBirth} onChange={v => patch({ dateOfBirth: v })} /></div>
                  <div>
                    <Label>{t("Photo")}</Label>
                    <AttachButton label="Upload photo" />
                  </div>
                  <div><Label tag="OPTIONAL">{t("Personal email")}</Label><TextInput type="email" value={r.personalEmail} onChange={v => patch({ personalEmail: v })} placeholder={t("name@example.com")} /></div>
                  <div><Label required>{t("Personal phone")}</Label><TextInput value={r.personalPhone} onChange={v => patch({ personalPhone: v })} placeholder="+91 90000 00000" /></div>
                </Grid3>

                <SubHead>{t("Emergency contacts")}</SubHead>
                <Helper>{t("Add at least two, in case the first is unreachable.")}</Helper>
                <div className="mt-3">
                  {r.emergencyContacts.map(c => (
                    <RepeatCard
                      key={c.id}
                      label="Emergency contact"
                      extra={
                        <label className="flex items-center gap-1.5 text-[11px] text-slate-500">
                          <input
                            type="checkbox"
                            checked={c.isPrimary}
                            onChange={() => patch({
                              emergencyContacts: r.emergencyContacts.map(x => ({ ...x, isPrimary: x.id === c.id })),
                            })}
                          />
                          {t("Primary")}
                        </label>
                      }
                      onRemove={() => patch({ emergencyContacts: r.emergencyContacts.filter(x => x.id !== c.id) })}
                    >
                      <Grid3>
                        <div><Label>{t("Name")}</Label><TextInput value={c.name} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, name: v } : x) })} placeholder={t("Full name")} /></div>
                        <div><Label>{t("Relationship")}</Label><Select value={c.relationship} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, relationship: v } : x) })} options={RELATIONSHIPS} /></div>
                        <div><Label>{t("Phone")}</Label><TextInput value={c.phone} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, phone: v } : x) })} placeholder="+91 90000 00000" /></div>
                        <div><Label tag="OPTIONAL">{t("Alternate phone")}</Label><TextInput value={c.altPhone} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, altPhone: v } : x) })} /></div>
                        <div><Label tag="OPTIONAL">{t("Email")}</Label><TextInput value={c.email} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, email: v } : x) })} /></div>
                        <div><Label tag="OPTIONAL">{t("Address")}</Label><TextInput value={c.address} onChange={v => patch({ emergencyContacts: r.emergencyContacts.map(x => x.id === c.id ? { ...x, address: v } : x) })} /></div>
                      </Grid3>
                    </RepeatCard>
                  ))}
                  <AddButton label="Add emergency contact" onClick={() => patch({
                    emergencyContacts: [...r.emergencyContacts, { id: nextId(), name: "", relationship: "", phone: "", altPhone: "", email: "", address: "", isPrimary: r.emergencyContacts.length === 0 }],
                  })} />
                </div>
              </>
            )}

            {/* 2. Employment */}
            {step === 1 && (
              <>
                <SectionTitle a="Employment" b="details" sub="Role, reporting line, work setup and pay." />
                <Grid3>
                  <div><Label required>{t("Date of joining")}</Label><DateInput value={r.dateOfJoining} onChange={v => patch({ dateOfJoining: v })} /></div>
                  <div>
                    <Label tag="ASSIGN WHEN READY">{t("Work email")}</Label>
                    <TextInput value={r.workEmail} onChange={v => patch({ workEmail: v })} placeholder={t("name@company.com")} />
                    <Helper>{t("Separate from the personal email used for preboarding.")}</Helper>
                  </div>
                  <div><Label required>{t("Employment type")}</Label><Select value={r.employmentType} onChange={v => patch({ employmentType: v })} options={["Permanent", "Contract", "Part-Time", "Intern", "Consultant"]} /></div>

                  <div><Label>{t("Probation period")}</Label><Select value={r.probationMonths ? `${r.probationMonths} months` : ""} onChange={v => patch({ probationMonths: v.split(" ")[0] })} options={["3 months", "6 months", "12 months"]} /></div>
                  <div><Label tag="AUTO">{t("Confirmation date")}</Label><DateInput readOnly value={addMonths(r.dateOfJoining, Number(r.probationMonths) || 0)} onChange={() => {}} /></div>
                  <div><Label>{t("Notice period")}</Label><Select value={r.noticeDays ? `${r.noticeDays} days` : ""} onChange={v => patch({ noticeDays: v.split(" ")[0] })} options={["30 days", "60 days", "90 days"]} /></div>
                </Grid3>

                <SubHead>Position &amp; reporting</SubHead>
                <Grid3>
                  <div><Label required>{t("Position")}</Label><Select value={r.position} onChange={v => patch({ position: v })} options={["VP, Engineering", "Engineering Manager", "Senior Software Engineer", "Software Engineer"]} /></div>
                  <div><Label tag="FROM POSITION">{t("Org unit")}</Label><Select readOnly value="Software Services › Leadership" onChange={() => {}} options={[]} /></div>
                  <div><Label tag="FROM POSITION">{t("Grade / band")}</Label><Select readOnly value="L2 · Associate" onChange={() => {}} options={[]} /></div>

                  <div>
                    <Label required tag="FROM UNIT">{t("Reporting manager")}</Label>
                    <Select value={r.reportingManager} onChange={v => patch({ reportingManager: v })} options={["CEO Office", "VP, Engineering", "Engineering Manager"]} />
                    {!r.reportingManager && <Helper tone="red">{t("No manager mapped to this unit — assign later and HR will set it.")}</Helper>}
                  </div>
                  <div>
                    <Label tag="OPTIONAL">{t("Dotted-line manager")}</Label>
                    <Select value={r.dottedLineManager} onChange={v => patch({ dottedLineManager: v })} options={["CEO Office", "VP, Engineering"]} />
                    <Helper>{t("Any unit — cross-functional reporting.")}</Helper>
                  </div>
                  <div><Label tag="FROM UNIT">{t("Cost center")}</Label><Select readOnly value="CC-ENG-004" onChange={() => {}} options={[]} /></div>
                </Grid3>

                <SubHead>{t("Work setup")}</SubHead>
                <Grid3>
                  <div><Label required>{t("Work location")}</Label><Select value={r.workLocation} onChange={v => patch({ workLocation: v })} options={["Gachibowli", "Bengaluru", "Pune", "Remote"]} /></div>
                  <div><Label>{t("Work mode")}</Label><Select value={r.workMode} onChange={v => patch({ workMode: v })} options={["Office", "Hybrid", "Remote"]} /></div>
                  <div><Label>{t("Shift")}</Label><Select value={r.shift} onChange={v => patch({ shift: v })} options={["General 09:30–18:30", "Early 07:00–15:30", "Night 22:00–06:00"]} /></div>

                  <div>
                    <Label>{t("Weekly off")}</Label>
                    <div className="flex flex-wrap gap-2">
                      {["Saturday", "Sunday", "Friday"].map(day => (
                        <button
                          key={day}
                          type="button"
                          onClick={() => patch({ weeklyOff: r.weeklyOff.includes(day) ? r.weeklyOff.filter(d => d !== day) : [...r.weeklyOff, day] })}
                          className="px-2.5 py-1 rounded-full text-[11.5px] border"
                          style={r.weeklyOff.includes(day) ? { background: PURPLE, color: "#fff", borderColor: PURPLE } : { borderColor: "#e2e8f0", color: "#475569" }}
                        >
                          {day}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div><Label required>{t("Attendance scheme")}</Label><Select value={r.attendanceScheme} onChange={v => patch({ attendanceScheme: v })} options={["Standard – Office", "Flexible", "Shift-based"]} /></div>
                  <div><Label required>{t("Leave plan")}</Label><Select value={r.leavePlan} onChange={v => patch({ leavePlan: v })} options={["Standard India Leave Policy", "Senior Leadership Leave Policy"]} /></div>
                </Grid3>

                <SubHead>{t("Compensation")}</SubHead>
                <Grid3>
                  <div><Label>{t("Pay group")}</Label><Select readOnly value="Monthly – India" onChange={() => {}} options={[]} /></div>
                  <div><Label tag="OPTIONAL">{t("Salary structure")}</Label><Select value={r.salaryStructure} onChange={v => patch({ salaryStructure: v })} options={["Standard India CTC", "Leadership CTC"]} /></div>
                  <div>
                    <Label tag="HR" onSuggest={() => patch({ annualCtc: "3420000" })}>{t("Annual fixed CTC")}</Label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-[13px]">₹</span>
                      <input
                        type="number"
                        value={r.annualCtc}
                        onChange={e => patch({ annualCtc: e.target.value })}
                        className={`${inputBase} pl-6 bg-white`}
                      />
                    </div>
                    <Helper>{t("Total fixed cost to company per year, before any statutory deductions.")}</Helper>
                  </div>
                </Grid3>
              </>
            )}

            {/* 3. Basic pay */}
            {step === 2 && (
              <>
                <SectionTitle a="Basic" b="pay" sub="Pay scale and the wage types that make up the monthly salary." />
                <div className="flex flex-wrap items-center gap-3 mb-5 text-[11px] text-slate-500 bg-slate-50 rounded-lg px-3 py-2">
                  <span className="font-bold uppercase tracking-wide text-[10px] text-slate-400">{t("Who maintains:")}</span>
                  <span className="flex items-center gap-1"><Pill tone="purple">HR</Pill> {t("pay structure and amounts")}</span>
                  <span className="flex items-center gap-1"><Pill tone="blue">{t("HR / Employee")}</Pill> {t("employee may self-declare")}</span>
                  <span className="flex items-center gap-1"><Pill tone="amber">{t("Admin")}</Pill> {t("configuration, locked")}</span>
                </div>

                <SubHead>{t("Validity")} <Pill tone="purple">HR</Pill></SubHead>
                <Grid3>
                  <div><Label tag="FROM JOINING DATE">{t("Valid from")}</Label><DateInput readOnly value={r.dateOfJoining} onChange={() => {}} /></div>
                  <div><Label>{t("Valid to")}</Label><DateInput readOnly value="9999-12-31" onChange={() => {}} /></div>
                  <div><Label>{t("Reason")}</Label><TextInput readOnly value="Initial basic pay" onChange={() => {}} /></div>
                </Grid3>

                <SubHead>Pay scale &amp; payroll area <Pill tone="amber">{t("Admin")}</Pill></SubHead>
                <Grid3>
                  <div><Label>{t("Payroll area")}</Label><TextInput readOnly value="IN01 — India Monthly" onChange={() => {}} /></div>
                  <div><Label>{t("Working hours / period")}</Label><TextInput readOnly value="180.00" onChange={() => {}} /></div>
                  <div><Label>{t("Capacity utilisation")}</Label><TextInput readOnly value="100%" onChange={() => {}} /></div>
                  <div><Label tag="HR">{t("Pay scale group")}</Label><Select value={r.payScaleGroup} onChange={v => patch({ payScaleGroup: v })} options={["L1", "L2", "L3", "L4"]} /></div>
                  <div><Label tag="HR">{t("Pay scale level")}</Label><Select value={r.payScaleLevel} onChange={v => patch({ payScaleLevel: v })} options={["Associate", "Senior Associate", "Lead"]} /></div>
                  <div>
                    <Label tag="HR">{t("Basic as % of CTC")}</Label>
                    <Select value={`${r.basicPctOfCtc}%`} onChange={v => patch({ basicPctOfCtc: v.replace("%", "") })} options={["35%", "40%", "45%", "50%"]} />
                    <Helper>{t("The Code on Wages moves this floor toward 50%.")}</Helper>
                  </div>
                </Grid3>

                <div className="mt-5 text-[11.5px] text-slate-500 bg-violet-50 rounded-lg px-3 py-2.5">
                  {t("Monthly amounts derived from the annual CTC in Employment. Any earning can be overridden; Special Allowance balances back to CTC and the statutory rows recalculate.")}
                </div>

                <PayTable
                  title={t("Earnings")}
                  tag={{ text: "HR", tone: "purple" }}
                  rows={[
                    ["1000", "Basic Pay", pay.basic, "40% of CTC"],
                    ["1010", "Dearness Allowance", pay.da, "Counts as wages with Basic"],
                    ["1100", "House Rent Allowance", pay.hra, "40% of Basic+DA — non-metro"],
                    ["1200", "Conveyance Allowance", pay.conveyance, "Legacy — subsumed into standard deduction"],
                    ["1300", "Medical Allowance", pay.medical, "Legacy — subsumed into standard deduction"],
                    ["1350", "Leave Travel Allowance", pay.lta, "8.33% of Basic+DA"],
                    ["1400", "Special Allowance", pay.specialAllowance, "Balances earnings to CTC", true],
                  ]}
                />
                <PayTable
                  title={t("Employer contributions")}
                  tag={{ text: "Statutory", tone: "amber" }}
                  rows={[
                    ["5000", "Employer PF (EPF)", pay.employerPf, "3.67% of Basic+DA, ₹15,000 ceiling", true],
                    ["5010", "Employer Pension (EPS)", pay.employerEps, "8.33% of Basic+DA, ₹15,000 ceiling", true],
                    ["5100", "Gratuity Provision", pay.gratuity, "4.81% of Basic+DA", true],
                    ["5200", "Employer ESI", pay.employerEsi, "3.25% of gross", true],
                  ]}
                />
                <PayTable
                  title={t("Statutory deductions")}
                  tag={{ text: "Statutory", tone: "amber" }}
                  rows={[
                    ["6000", "Employee PF", pay.employeePf, "12% of Basic+DA, ₹15,000 ceiling", true],
                    ["6100", "Employee ESI", pay.employeeEsi, "0.75% of gross", true],
                    ["6200", "Professional Tax", pay.professionalTax, `${r.workLocation || "[State]"} slab (from work location)`, true],
                  ]}
                />

                <div className="mt-5 rounded-lg border border-slate-200 divide-y divide-slate-100">
                  {[
                    ["Monthly gross", pay.monthlyGross, "paid to the employee"],
                    ["Employer contributions", pay.employerContributions, "on top of gross"],
                    ["Monthly cost to company", pay.costToCompany, ""],
                    ["Annual cost to company", pay.annualCostToCompany, ""],
                    ["Statutory deductions", -pay.statutoryDeductions, ""],
                    ["Net take-home before income tax", pay.netTakeHome, ""],
                  ].map(([label, amt, note]) => (
                    <div key={label as string} className="flex items-center justify-between px-4 py-2.5">
                      <div>
                        <span className="text-[12.5px] text-slate-700">{t(String(label))}</span>
                        {note ? <span className="text-[11px] text-slate-400 ml-2">{t(note as string)}</span> : null}
                      </div>
                      <span className={`text-[13px] font-bold ${Number(amt) < 0 ? "text-red-500" : "text-slate-800"}`}>
                        {Number(amt) < 0 ? `–${inr(Math.abs(Number(amt)))}` : inr(Number(amt))}
                      </span>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => patch({ basicPctOfCtc: "40" })}
                  className="w-full mt-4 py-2.5 rounded-lg border border-slate-200 text-[12.5px] font-semibold text-slate-600"
                >
                  {t("Reset to derived amounts")}
                </button>

                <SubHead>{t("Employee declarations")} <Pill tone="blue">{t("HR / Employee")}</Pill></SubHead>
                <Grid3>
                  <div><Label>{t("Tax regime")}</Label><Select value={r.taxRegime} onChange={v => patch({ taxRegime: v })} options={["New regime (115BAC)", "Old regime"]} /></div>
                  <div><Label>{t("Payment method")}</Label><TextInput readOnly value="Bank transfer – NEFT" onChange={() => {}} /></div>
                </Grid3>
              </>
            )}

            {/* 4. Statutory & accounts */}
            {step === 3 && (
              <>
                <SectionTitle a="Statutory &amp;" b="accounts" sub="Government IDs, provident fund, ESI and bank details." />
                <div className="mb-5 rounded-lg px-3.5 py-3 text-[12px]" style={{ background: "#f3e8ff", color: "#5b21b6" }}>
                  <b>{t("Handled as sensitive data —")}</b> Government IDs and bank details are stored encrypted, masked in the UI by
                  default, and every reveal is written to the audit log under the DPDP Act 2023.
                </div>

                <SubHead>{t("Government IDs")}</SubHead>
                <Grid3>
                  <div>
                    <Label required>PAN</Label>
                    <RevealField value={r.pan} onChange={v => patch({ pan: v.toUpperCase() })} placeholder={t("ABCDE1234F")} />
                    <AttachButton label="Attach PAN card" />
                  </div>
                  <div>
                    <Label required>{t("Aadhaar")}</Label>
                    <RevealField value={r.aadhaar} onChange={v => patch({ aadhaar: v.replace(/\D/g, "") })} placeholder={t("XXXX XXXX XXXX")} />
                    <AttachButton label="Attach Aadhaar" />
                  </div>
                  <div><Label tag="OPTIONAL" onSuggest={() => patch({ nameAsPerPan: r.fullName })}>{t("Name as per PAN")}</Label><TextInput value={r.nameAsPerPan} onChange={v => patch({ nameAsPerPan: v })} /></div>

                  <div>
                    <Label tag="OPTIONAL">{t("Passport number")}</Label>
                    <TextInput value={r.passportNumber} onChange={v => patch({ passportNumber: v })} />
                    <AttachButton label="Attach passport" />
                  </div>
                  <div><Label tag="OPTIONAL">{t("Passport expiry")}</Label><DateInput value={r.passportExpiry} onChange={v => patch({ passportExpiry: v })} disabled={!r.passportNumber} /></div>
                  <div><Label>{t("Residential status")}</Label><Select value={r.residentialStatus} onChange={v => patch({ residentialStatus: v })} options={["Resident", "Non-resident"]} /></div>
                </Grid3>

                <SubHead>{t("Provident fund")}</SubHead>
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-[12.5px] text-slate-700">{t("Covered under PF")}</span>
                  <Toggle value={r.pfCovered} onChange={v => patch({ pfCovered: v })} />
                </div>
                <Grid3>
                  <div>
                    <Label tag="OPTIONAL">UAN</Label>
                    <TextInput value={r.uan} onChange={v => patch({ uan: v.replace(/\D/g, "") })} />
                    <Helper>{t("Leave blank for a first job — EPFO will allot one.")}</Helper>
                  </div>
                  <div><Label tag="OPTIONAL">{t("PF number")}</Label><TextInput value={r.pfNumber} onChange={v => patch({ pfNumber: v })} /></div>
                  <div><Label tag="OPTIONAL" onSuggest={() => patch({ nameOnPf: r.fullName })}>{t("Name on PF account")}</Label><TextInput value={r.nameOnPf} onChange={v => patch({ nameOnPf: v })} /></div>
                  <div><Label>{t("Contribution")}</Label><Select value={r.pfContribution} onChange={v => patch({ pfContribution: v })} options={["EPF + EPS", "EPF only"]} /></div>
                  <div><Label tag="COMPANY">{t("Employer PF code")}</Label><TextInput readOnly value="BGPF0012345" onChange={() => {}} /></div>
                </Grid3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-5 pt-5 border-t border-slate-100">
                  <div>
                    <div className="text-[10.5px] font-bold tracking-wider uppercase text-slate-400 mb-3">ESI</div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-[12.5px] text-slate-700">{t("Covered under ESI")}</span>
                      <Toggle value={r.esiCovered} onChange={v => patch({ esiCovered: v })} />
                    </div>
                    <Helper>{t("Switches on automatically when gross wage falls below the ESI threshold.")}</Helper>
                  </div>
                  <div>
                    <div className="text-[10.5px] font-bold tracking-wider uppercase text-slate-400 mb-3">Professional tax &amp; LWF</div>
                    <div className="mb-3"><Label tag="FROM LOCATION">{t("PT state")}</Label><TextInput readOnly value={r.workLocation ? "Telangana" : ""} onChange={() => {}} /></div>
                    <div className="flex items-center gap-3">
                      <span className="text-[12.5px] text-slate-700">{t("LWF applicable")}</span>
                      <Toggle value={r.lwfApplicable} onChange={v => patch({ lwfApplicable: v })} />
                    </div>
                  </div>
                </div>

                <SubHead>{t("Bank account")}</SubHead>
                <Grid3>
                  <div><Label required onSuggest={() => patch({ accountHolderName: r.fullName })}>{t("Account holder name")}</Label><TextInput value={r.accountHolderName} onChange={v => patch({ accountHolderName: v })} /></div>
                  <div>
                    <Label required>{t("Account number")}</Label>
                    <RevealField value={r.accountNumber} onChange={v => patch({ accountNumber: v.replace(/\D/g, "") })} />
                    <AttachButton label="Attach cancelled cheque" />
                  </div>
                  <div>
                    <Label required>{t("Confirm account number")}</Label>
                    <TextInput value={r.confirmAccountNumber} onChange={v => patch({ confirmAccountNumber: v.replace(/\D/g, "") })} />
                    {r.confirmAccountNumber && (
                      r.confirmAccountNumber === r.accountNumber
                        ? <Helper tone="green">{t("Matches")}</Helper>
                        : <Helper tone="red">Account numbers don&apos;t match.</Helper>
                    )}
                  </div>
                  <div>
                    <Label required>{t("IFSC code")}</Label>
                    <TextInput value={r.ifscCode} onChange={v => patch({ ifscCode: v.toUpperCase() })} />
                    {/^[A-Z]{4}0[A-Z0-9]{6}$/.test(r.ifscCode) && <Helper tone="green">{t("Detected: HDFC Bank")}</Helper>}
                  </div>
                  <div><Label tag="FROM IFSC">{t("Bank")}</Label><TextInput readOnly value={/^[A-Z]{4}0[A-Z0-9]{6}$/.test(r.ifscCode) ? "HDFC Bank" : ""} onChange={() => {}} /></div>
                </Grid3>
              </>
            )}

            {/* 5. Family & nomination */}
            {step === 4 && (
              <>
                <SectionTitle a="Family &amp;" b="nomination" sub="Dependants, EPF nominees and guardian details." />

                <SubHead>{t("Family members")}</SubHead>
                <Helper>Nominees are chosen from this list, and the parents&apos; names on step 1 are filled from it. Add family before setting nominations.</Helper>
                <div className="mt-3">
                  {r.familyMembers.map(m => (
                    <RepeatCard key={m.id} label="Family member" onRemove={() => patch({ familyMembers: r.familyMembers.filter(x => x.id !== m.id), nominees: r.nominees.filter(n => n.familyMemberId !== m.id) })}>
                      <Grid3>
                        <div><Label>{t("Name")}</Label><TextInput value={m.name} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, name: v } : x) })} placeholder={t("Full name")} /></div>
                        <div><Label>{t("Relationship")}</Label><Select value={m.relationship} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, relationship: v } : x) })} options={RELATIONSHIPS} /></div>
                        <div><Label>{t("Date of birth")}</Label><DateInput value={m.dob} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, dob: v } : x) })} /></div>
                        <div><Label>{t("Gender")}</Label><Select value={m.gender} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, gender: v } : x) })} options={["Male", "Female", "Other"]} /></div>
                        <div><Label>{t("Blood group")}</Label><TextInput value={m.bloodGroup} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, bloodGroup: v } : x) })} placeholder={t("e.g. O+")} /></div>
                        <div><Label>{t("Dependent")}</Label><Select value={m.isDependent === "yes" ? "Yes" : "No"} onChange={v => patch({ familyMembers: r.familyMembers.map(x => x.id === m.id ? { ...x, isDependent: v === "Yes" ? "yes" : "no" } : x) })} options={["Yes", "No"]} /></div>
                      </Grid3>
                    </RepeatCard>
                  ))}
                  <AddButton label="Add family member" onClick={() => patch({ familyMembers: [...r.familyMembers, { id: nextId(), name: "", relationship: "", dob: "", gender: "", bloodGroup: "", isDependent: "no" }] })} />
                </div>

                <SubHead>{t("Nomination")}</SubHead>
                <Helper>{t("Required for EPF Form 2. Nominees are picked from the family list, so a name is only typed once. Each scheme should total 100%.")}</Helper>
                <div className="mt-3">
                  {r.nominees.map(n => (
                    <RepeatCard key={n.id} label="Nominee" onRemove={() => patch({ nominees: r.nominees.filter(x => x.id !== n.id) })}>
                      <Grid3>
                        <div>
                          <Label>{t("Nominee")}</Label>
                          <Select value={familyName(n.familyMemberId)} onChange={() => {}} options={r.familyMembers.map(m => `${m.name} (${m.relationship})`)} placeholder={t("Select from family")} />
                          <select
                            className="sr-only"
                            value={n.familyMemberId}
                            onChange={e => patch({ nominees: r.nominees.map(x => x.id === n.id ? { ...x, familyMemberId: e.target.value } : x) })}
                          >
                            <option value="">{t("Select from family")}</option>
                            {r.familyMembers.map(m => <option key={m.id} value={m.id}>{m.name} ({m.relationship})</option>)}
                          </select>
                        </div>
                        <div><Label tag="AUTO">{t("Relationship")}</Label><TextInput readOnly value={familyRelationship(n.familyMemberId) ? `From family record — ${familyRelationship(n.familyMemberId)}` : "From family record"} onChange={() => {}} /></div>
                        <div><Label>{t("Scheme")}</Label><Select value={n.scheme} onChange={v => patch({ nominees: r.nominees.map(x => x.id === n.id ? { ...x, scheme: v } : x) })} options={SCHEMES} /></div>
                        <div><Label>{t("Share %")}</Label><TextInput type="number" value={n.sharePercent} onChange={v => patch({ nominees: r.nominees.map(x => x.id === n.id ? { ...x, sharePercent: v } : x) })} /></div>
                      </Grid3>
                    </RepeatCard>
                  ))}
                  <AddButton label="Add nominee" onClick={() => patch({ nominees: [...r.nominees, { id: nextId(), familyMemberId: "", scheme: "EPF + EPS", sharePercent: "" }] })} />
                  <div className="flex justify-end mt-2">
                    <span className={`text-[12px] font-semibold ${schemeShareTotals.every(s => s.total === 100 || s.total === 0) ? "text-emerald-600" : "text-red-500"}`}>
                      {schemeShareTotals.map(s => `${s.scheme} ${s.total}%`).join(" · ")}
                    </span>
                  </div>
                </div>

                <SubHead>{t("Guardian")}</SubHead>
                <Helper>{t("Only required if a nominee above is under 18.")}</Helper>
                <Grid3>
                  <div><Label tag="OPTIONAL" onSuggest={() => patch({ guardianName: "" })}>{t("Guardian name")}</Label><TextInput value={r.guardianName} onChange={v => patch({ guardianName: v })} /></div>
                  <div><Label tag="OPTIONAL" onSuggest={() => patch({ guardianRelationship: "" })}>{t("Relationship")}</Label><TextInput value={r.guardianRelationship} onChange={v => patch({ guardianRelationship: v })} /></div>
                  <div><Label tag="OPTIONAL">{t("Guardian address")}</Label><TextInput value={r.guardianAddress} onChange={v => patch({ guardianAddress: v })} /></div>
                </Grid3>
              </>
            )}

            {/* 6. Education & experience */}
            {step === 5 && (
              <>
                <SectionTitle a="Education &" b="experience" sub="Qualifications and previous employers." />

                <SummaryStrip items={[
                  ["Qualifications", String(r.qualifications.length)],
                  ["Highest", r.qualifications.find(q => q.isHighest)?.level ?? "—"],
                  ["Institution", r.qualifications.find(q => q.isHighest)?.institution ?? "—"],
                  ["Specialization", r.qualifications.find(q => q.isHighest)?.specialization ?? "—"],
                  ["Grade", r.qualifications.find(q => q.isHighest)?.gradeOrPercentage ?? "—"],
                  ["Completed", r.qualifications.find(q => q.isHighest)?.endDate ?? "—"],
                ]} />
                <Helper>{t("Add at least one qualification. Mark the highest so reports can group by it.")}</Helper>
                <div className="mt-3">
                  {r.qualifications.map(q => (
                    <RepeatCard
                      key={q.id} label="Qualification"
                      extra={
                        <label className="flex items-center gap-1.5 text-[11px] text-slate-500">
                          <input type="checkbox" checked={q.isHighest} onChange={() => patch({ qualifications: r.qualifications.map(x => ({ ...x, isHighest: x.id === q.id })) })} />
                          {t("Highest")}
                        </label>
                      }
                      onRemove={() => patch({ qualifications: r.qualifications.filter(x => x.id !== q.id) })}
                    >
                      <Grid3>
                        <div><Label>{t("Education level")}</Label><Select value={q.level} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, level: v } : x) })} options={["Bachelor's", "Master's", "Doctorate", "Diploma"]} /></div>
                        <div><Label>{t("Institution")}</Label><TextInput value={q.institution} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, institution: v } : x) })} placeholder={t("Institution name")} /></div>
                        <div><Label tag="OPTIONAL">{t("Specialization")}</Label><TextInput value={q.specialization} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, specialization: v } : x) })} /></div>
                        <div><Label>{t("Percentage / grade")}</Label><TextInput value={q.gradeOrPercentage} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, gradeOrPercentage: v } : x) })} placeholder={t("e.g. 72% or CGPA")} /></div>
                        <div><Label>{t("Start date")}</Label><DateInput value={q.startDate} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, startDate: v } : x) })} /></div>
                        <div><Label>{t("End date")}</Label><DateInput value={q.endDate} onChange={v => patch({ qualifications: r.qualifications.map(x => x.id === q.id ? { ...x, endDate: v } : x) })} /></div>
                      </Grid3>
                      <AttachButton label="Attach certificate" />
                    </RepeatCard>
                  ))}
                  <AddButton label="Add qualification" onClick={() => patch({ qualifications: [...r.qualifications, { id: nextId(), level: "", institution: "", specialization: "", gradeOrPercentage: "", startDate: "", endDate: "", isHighest: false }] })} />
                </div>

                <SubHead>{t("Work experience")}</SubHead>
                <SummaryStrip items={[
                  ["Employers", String(r.experiences.length)],
                  ["Total experience", totalExperienceLabel],
                  ["Most recent", r.experiences[0] ? `${r.experiences[0].designation} · ${r.experiences[0].employer}` : "—"],
                  ["Last working day", r.experiences[0]?.lastWorkingDay ?? "—"],
                ]} />
                <Helper>{t("Leave empty for a fresher — total experience reads zero. Experience is counted up to the joining date.")}</Helper>
                <div className="mt-3">
                  {r.experiences.map(e => (
                    <RepeatCard key={e.id} label="Experience" onRemove={() => patch({ experiences: r.experiences.filter(x => x.id !== e.id) })}>
                      <Grid3>
                        <div><Label>{t("Employer")}</Label><TextInput value={e.employer} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, employer: v } : x) })} placeholder={t("Company name")} /></div>
                        <div><Label>{t("Designation")}</Label><TextInput value={e.designation} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, designation: v } : x) })} placeholder={t("Job title")} /></div>
                        <div><Label>{t("Employment type")}</Label><Select value={e.employmentType} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, employmentType: v } : x) })} options={["Full-time", "Part-time", "Contract", "Internship"]} /></div>
                        <div><Label>{t("Start date")}</Label><DateInput value={e.startDate} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, startDate: v } : x) })} /></div>
                        <div>
                          <Label>{t("Last working day")}</Label>
                          <DateInput value={e.lastWorkingDay} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, lastWorkingDay: v } : x) })} />
                          <Helper>{t("Actual, or expected if serving notice.")}</Helper>
                        </div>
                        <div><Label tag="OPTIONAL">{t("Reason for leaving")}</Label><TextInput value={e.reason} onChange={v => patch({ experiences: r.experiences.map(x => x.id === e.id ? { ...x, reason: v } : x) })} /></div>
                      </Grid3>
                      <AttachButton label="Attach experience letter" />
                    </RepeatCard>
                  ))}
                  <AddButton label="Add previous employer" onClick={() => patch({ experiences: [...r.experiences, { id: nextId(), employer: "", designation: "", employmentType: "Full-time", startDate: "", lastWorkingDay: "", reason: "" }] })} />
                </div>

                <SubHead>Skills &amp; certifications</SubHead>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                  <div className="md:col-span-2">
                    <Label tag="OPTIONAL">{t("Core skills")}</Label>
                    <TextInput value={r.coreSkills} onChange={v => patch({ coreSkills: v })} placeholder={t("e.g. React, payroll operations, team leadership")} />
                    <Helper>Use comma-separated skills; keep this relevant to the role.</Helper>
                  </div>
                  <div><Label tag="OPTIONAL">{t("Certifications")}</Label><TextInput value={r.certifications} onChange={v => patch({ certifications: v })} placeholder={t("Certification and year")} /></div>
                </div>
              </>
            )}

            {/* 7. Documents */}
            {step === 6 && (
              <>
                <SectionTitle a="Joining" b="documents" sub="Upload the paperwork needed to complete onboarding." />
                <Helper>
                  {t("PDF, JPG or PNG, max 5 MB each. Anything already attached beside its field in an earlier step shows here automatically — no need to upload it twice. Remaining items can also be completed after the record is created.")}
                </Helper>

                <DocGroup title={t("Identity")} docs={[
                  { name: "PAN Card", required: true, uploaded: !!r.pan },
                  { name: "Aadhaar Card", required: true, uploaded: !!r.aadhaar },
                  { name: "Passport", required: false, uploaded: !!r.passportNumber },
                ]} />
                <DocGroup title={t("Education & experience")} docs={[
                  { name: "Degree Certificate", required: true, uploaded: r.qualifications.length > 0 },
                  { name: "Experience Letter", required: false, uploaded: false },
                ]} />
                <DocGroup title={t("Financial")} docs={[
                  { name: "Cancelled Cheque", required: true, uploaded: !!r.accountNumber },
                  { name: "Latest Payslips", required: false, uploaded: false },
                ]} />
                <DocGroup title={t("Onboarding")} docs={[
                  { name: "Signed Offer Letter", required: true, uploaded: false },
                  { name: "Address Proof", required: false, uploaded: false },
                ]} />

                <SubHead>{t("Background verification")}</SubHead>
                <Grid3>
                  <div><Label>{t("Verification status")}</Label><Select value={r.verificationStatus} onChange={v => patch({ verificationStatus: v })} options={["Not initiated", "In progress", "Verified", "Failed"]} /></div>
                  <div><Label tag="IF VERIFIED">{t("Completed on")}</Label><DateInput value={r.verificationCompletedOn} onChange={v => patch({ verificationCompletedOn: v })} disabled={r.verificationStatus !== "Verified"} /></div>
                  <div><Label tag="OPTIONAL">{t("Provider / case reference")}</Label><TextInput value={r.verificationProvider} onChange={v => patch({ verificationProvider: v })} placeholder={t("Agency and reference")} /></div>
                </Grid3>
              </>
            )}

            {/* 8. Assets */}
            {step === 7 && (
              <>
                <SectionTitle a="Assets" b="to issue" sub="Laptop, phone and access card for day one." />
                <Helper>{t("Optional at hiring time — assets are usually issued on the joining date.")}</Helper>
                <div className="mt-3">
                  {r.assets.map(a => (
                    <RepeatCard key={a.id} label="Asset" onRemove={() => patch({ assets: r.assets.filter(x => x.id !== a.id) })}>
                      <Grid3>
                        <div><Label>{t("Asset")}</Label><Select value={a.assetType} onChange={v => patch({ assets: r.assets.map(x => x.id === a.id ? { ...x, assetType: v } : x) })} options={["Laptop", "Phone", "Monitor", "Headset", "SIM card"]} /></div>
                        <div><Label>{t("Tag / serial")}</Label><TextInput value={a.tagNumber} onChange={v => patch({ assets: r.assets.map(x => x.id === a.id ? { ...x, tagNumber: v } : x) })} /></div>
                        <div><Label>{t("Condition")}</Label><Select value={a.condition} onChange={v => patch({ assets: r.assets.map(x => x.id === a.id ? { ...x, condition: v } : x) })} options={["New", "Refurbished", "Used"]} /></div>
                      </Grid3>
                    </RepeatCard>
                  ))}
                  <AddButton label="Issue an asset" onClick={() => patch({ assets: [...r.assets, { id: nextId(), assetType: "", tagNumber: "", condition: "New" }] })} />
                </div>

                <SubHead>{t("Access card")}</SubHead>
                <Grid3>
                  <div><Label tag="OPTIONAL" onSuggest={() => patch({ cardNumber: "AC-" + Math.floor(Math.random() * 90000 + 10000) })}>{t("Card number")}</Label><TextInput value={r.cardNumber} onChange={v => patch({ cardNumber: v })} placeholder={t("Auto-generated if left blank")} /></div>
                  <div><Label>{t("Valid from")}</Label><DateInput value={r.cardValidFrom} onChange={v => patch({ cardValidFrom: v })} /></div>
                  <div><Label>{t("Valid till")}</Label><DateInput value={r.cardValidTill} onChange={v => patch({ cardValidTill: v })} /></div>
                </Grid3>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-3.5 border-t border-slate-100 bg-slate-50/60">
          <button onClick={() => { setR(seedDemoRecord()); setDirty(false); }} className="px-4 py-2 rounded-lg text-[13px] font-semibold text-slate-600">{t("Discard")}</button>
          <button onClick={handleClose} className="px-4 py-2 rounded-lg text-[13px] font-semibold text-slate-600">{t("Cancel")}</button>
          <button
            onClick={() => setDirty(false)}
            className="px-5 py-2 rounded-lg text-[13px] font-semibold text-white"
            style={{ background: PURPLE }}
          >
            {t("Save changes")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── Small shared sub-components ─────────────────────────

function addMonths(dateStr: string, months: number): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + months);
  return d.toISOString().slice(0, 10);
}

function PayTable({ title, tag, rows }: { title: string; tag: { text: string; tone: "purple" | "amber" }; rows: [string, string, number, string, boolean?][] }) {
  const t = useT();
  const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
  return (
    <div className="mt-5">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10.5px] font-bold tracking-wider uppercase text-slate-400">{title}</span>
        <Pill tone={tag.tone}>{t(tag.text)}</Pill>
      </div>
      <div className="rounded-lg border border-slate-200 overflow-hidden">
        <div className="grid grid-cols-[60px_1fr_120px_1fr_70px] gap-2 px-3 py-2 bg-slate-50 text-[10px] font-bold uppercase tracking-wide text-slate-400">
          <span>{t("Code")}</span><span>{t("Description")}</span><span className="text-right">{t("Amount (₹)")}</span><span>{t("Basis")}</span><span />
        </div>
        {rows.map(([code, desc, amt, basis, readOnly]) => (
          <div key={code} className="grid grid-cols-[60px_1fr_120px_1fr_70px] gap-2 px-3 py-2 border-t border-slate-100 items-center">
            <span className="text-[12px] font-semibold" style={{ color: PURPLE }}>{code}</span>
            <span className="text-[12.5px] text-slate-700">{t(desc)}</span>
            {readOnly ? (
              <span className="text-[12.5px] text-slate-500 text-right">{inr(amt)}</span>
            ) : (
              <input type="number" defaultValue={Math.round(amt)} className="h-8 rounded-md border border-slate-200 px-2 text-[12.5px] text-right" />
            )}
            <span className="text-[11px] text-slate-400">{t(basis)}</span>
            <span className="flex justify-end"><Pill tone={readOnly ? "amber" : "purple"}>{readOnly ? t("Auto") : "HR"}</Pill></span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryStrip({ items }: { items: [string, string][] }) {
  const t = useT();
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg px-3.5 py-2.5 mb-2" style={{ background: "#f3e8ff" }}>
      {items.map(([label, value]) => (
        <div key={label}>
          <div className="text-[9px] font-bold tracking-wider uppercase" style={{ color: PURPLE }}>{t(label)}</div>
          <div className="text-[12.5px] font-semibold text-slate-700">{value}</div>
        </div>
      ))}
    </div>
  );
}

function DocGroup({ title, docs }: { title: string; docs: { name: string; required: boolean; uploaded: boolean }[] }) {
  const t = useT();
  return (
    <div className="mt-4">
      <div className="text-[10.5px] font-bold tracking-wider uppercase text-slate-400 mb-2">{title}</div>
      <div className="space-y-2">
        {docs.map(d => (
          <div key={d.name} className="flex items-center justify-between rounded-lg border border-slate-200 px-3.5 py-2.5">
            <div className="flex items-center gap-2">
              <span className="text-[12.5px] text-slate-700">{t(d.name)}</span>
              <Pill tone={d.required ? "red" : "grey"}>{d.required ? t("Required") : t("Optional")}</Pill>
            </div>
            <div className="flex items-center gap-3">
              <Pill tone={d.uploaded ? "green" : "amber"}>{d.uploaded ? t("Uploaded") : t("Pending")}</Pill>
              <button type="button" className="px-2.5 py-1 rounded-md border border-slate-200 text-[11px] text-slate-600">{t("Choose file")}</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
