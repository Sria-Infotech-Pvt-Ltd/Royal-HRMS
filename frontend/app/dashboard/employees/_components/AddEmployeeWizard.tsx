"use client";

import { useState, type ReactNode } from "react";
import { addEmployee, DEPARTMENT_OPTIONS, type Employee, type Gender, type EmployeeStatus } from "../_data";

/* ══════════════════════════════════════════════════════════════
   CONSTANTS
══════════════════════════════════════════════════════════════ */
const STEPS = [
  { id: 1, short: "Pers...", label: "Personal Information",   icon: "ti-user",             sub: "Tell us about yourself" },
  { id: 2, short: "Empl...", label: "Employment Details",     icon: "ti-id",               sub: "Your role and work schedule" },
  { id: 3, short: "Addr...", label: "Address Details",        icon: "ti-map-pin",          sub: "Where do you live?" },
  { id: 4, short: "Educ...", label: "Education & Experience", icon: "ti-school",           sub: "Your qualifications and work history" },
  { id: 5, short: "Docu...", label: "Document Upload",        icon: "ti-file-description", sub: "Upload required documents" },
  { id: 6, short: "Bank...", label: "Bank Details",           icon: "ti-building-bank",    sub: "For salary credit" },
  { id: 7, short: "Revi...", label: "Review & Submit",        icon: "ti-checklist",        sub: "Verify everything before submitting" },
];
const TOTAL = STEPS.length;

const GENDERS       = ["Male", "Female", "Transgender"];
const BLOOD_GROUPS  = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const MARITAL_OPTS  = ["Single", "Married", "Divorced", "Widowed"];
const EMP_TYPES     = ["Permanent", "Contract", "Intern", "Probation"];
const EMP_STATUSES  = ["Probation", "Confirmed", "Active", "On Notice"];
const SHIFTS        = ["General (9-6)", "Morning (6-2)", "Evening (2-10)", "Night (10-6)"];
const WORK_TYPES    = ["Office", "WFH", "Hybrid"];
const ENTRY_SOURCES = ["Biometric", "Mobile App", "Web Portal", "Manual"];
const WEEKLY_DAYS   = ["5 Days (Mon–Fri)", "5.5 Days", "6 Days (Mon–Sat)"];
const CATEGORIES    = ["General", "OBC", "SC", "ST", "EWS"];
const DEGREES       = ["Bachelor of Engineering", "Bachelor of Science", "Bachelor of Commerce", "Master of Technology", "MBA", "PhD", "Diploma", "12th / HSC", "10th / SSC"];
const MODES         = ["Full-time", "Part-time", "Distance", "Online"];
const BANKS         = ["HDFC Bank", "SBI", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "Bank of Baroda", "Punjab National Bank", "Canara Bank"];
const ACCOUNT_TYPES = ["Savings", "Current", "Salary"];
const BRANCHES      = ["Head Office", "Bengaluru Branch", "Mumbai Branch", "Delhi Branch", "Chennai Branch", "Hyderabad Branch", "Pune Branch"];
const INDIA_STATES  = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana",
  "Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur",
  "Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana",
  "Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Jammu & Kashmir","Ladakh",
  "Chandigarh","Puducherry","Andaman & Nicobar Islands","Lakshadweep",
];

/* ══════════════════════════════════════════════════════════════
   TYPES
══════════════════════════════════════════════════════════════ */
type DocKey = "aadhaar" | "pan" | "degree" | "experience" | "offer" | "photo";

interface FormData {
  personal: {
    firstName: string; lastName: string; dob: string; gender: string;
    phone: string; altPhone: string; pan: string; aadhaar: string;
    marital: string; bloodGroup: string; ecName: string; ecPhone: string;
  };
  employment: {
    department: string; designation: string; branch: string;
    reportingManager: string; employeeType: string; employmentStatus: string;
    dateOfJoining: string; shift: string; workType: string;
    workEntrySource: string; weeklyDays: string; employeeCategory: string;
  };
  address: {
    street: string; city: string; pin: string; state: string; country: string;
    sameAsCurrent: boolean;
    pStreet: string; pCity: string; pPin: string; pState: string; pCountry: string;
  };
  education: {
    degree: string; specialisation: string; university: string;
    yearOfPassing: string; cgpa: string; mode: string;
    prevEmployer: string; prevDesignation: string;
    fromDate: string; toDate: string; reasonLeaving: string;
  };
  docs: Record<DocKey, boolean>;
  bank: {
    bankName: string; accountHolder: string; accountNumber: string;
    confirmAccount: string; ifsc: string; accountType: string;
    branchName: string; uan: string;
  };
  declaration: boolean;
}

const EMPTY: FormData = {
  personal: { firstName: "", lastName: "", dob: "", gender: "Male", phone: "", altPhone: "", pan: "", aadhaar: "", marital: "Single", bloodGroup: "B+", ecName: "", ecPhone: "" },
  employment: { department: DEPARTMENT_OPTIONS[0] ?? "Engineering", designation: "", branch: "Head Office", reportingManager: "", employeeType: "Permanent", employmentStatus: "Probation", dateOfJoining: "", shift: "General (9-6)", workType: "Office", workEntrySource: "Biometric", weeklyDays: "5 Days (Mon–Fri)", employeeCategory: "General" },
  address: { street: "", city: "", pin: "", state: "Karnataka", country: "India", sameAsCurrent: false, pStreet: "", pCity: "", pPin: "", pState: "Karnataka", pCountry: "India" },
  education: { degree: "Bachelor of Engineering", specialisation: "", university: "", yearOfPassing: "", cgpa: "", mode: "Full-time", prevEmployer: "", prevDesignation: "", fromDate: "", toDate: "", reasonLeaving: "" },
  docs: { aadhaar: false, pan: false, degree: false, experience: false, offer: false, photo: false },
  bank: { bankName: "HDFC Bank", accountHolder: "", accountNumber: "", confirmAccount: "", ifsc: "", accountType: "Savings", branchName: "", uan: "" },
  declaration: false,
};

/* ══════════════════════════════════════════════════════════════
   SHARED STYLES
══════════════════════════════════════════════════════════════ */
const INP     = "w-full px-3 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-white text-[var(--on-bg)] placeholder:text-[#a5b0c2] focus:outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(30,78,140,0.12)] transition-colors";
const INP_ERR = "w-full px-3 py-2.5 rounded-lg border border-[var(--error)] text-[13px] bg-white text-[var(--on-bg)] placeholder:text-[#a5b0c2] focus:outline-none focus:border-[var(--error)] focus:ring-2 focus:ring-[rgba(192,57,43,0.12)] transition-colors";
const SEL     = INP + " appearance-none pr-8 cursor-pointer";
const SS      = { backgroundImage:"url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>\")", backgroundRepeat:"no-repeat" as const, backgroundPosition:"right 8px center" as const, backgroundSize:"14px" as const };

/* ══════════════════════════════════════════════════════════════
   ATOMS
══════════════════════════════════════════════════════════════ */
function F({ label, opt, err, full, children }: { label: string; opt?: boolean; err?: string; full?: boolean; children: ReactNode }) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <label className={`block text-[12px] font-${opt ? "medium text-[var(--on-variant)]" : "semibold text-[var(--on-bg)]"} mb-1.5`}>
        {label}{!opt && <span className="ml-0.5" style={{ color: "var(--error)" }}>*</span>}
      </label>
      {children}
      {err && <p className="text-[11px] mt-1 font-medium" style={{ color: "var(--error)" }}>{err}</p>}
    </div>
  );
}

function In({ v, set, ph, type = "text", err }: { v: string; set: (x: string) => void; ph?: string; type?: string; err?: boolean }) {
  return <input type={type} value={v} onChange={e => set(e.target.value)} placeholder={ph} suppressHydrationWarning className={err ? INP_ERR : INP} />;
}

function Se({ v, set, children }: { v: string; set: (x: string) => void; children: ReactNode }) {
  return <select value={v} onChange={e => set(e.target.value)} className={SEL} style={SS} suppressHydrationWarning>{children}</select>;
}

function Divider({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 mt-4 mb-3">
      <i className={`ti ${icon} text-[13px]`} style={{ color: "var(--primary)" }} />
      <span className="text-[11.5px] font-bold uppercase tracking-wide" style={{ color: "var(--primary)" }}>{title}</span>
      <div className="flex-1 h-px" style={{ background: "var(--outline-v)" }} />
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP FORMS
══════════════════════════════════════════════════════════════ */
function Step1({ d, s, e }: { d: FormData["personal"]; s: (k: keyof FormData["personal"], v: string) => void; e: Record<string, string | undefined> }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <F label="First Name"            err={e.firstName}><In v={d.firstName} set={v => s("firstName", v)} ph="e.g. Priya"          err={!!e.firstName} /></F>
      <F label="Last Name"             err={e.lastName} ><In v={d.lastName}  set={v => s("lastName",  v)} ph="e.g. Sharma"         err={!!e.lastName}  /></F>
      <F label="Date of Birth"         err={e.dob}      ><In v={d.dob}       set={v => s("dob",       v)} type="date"              err={!!e.dob}       /></F>
      <F label="Gender" opt><Se v={d.gender}     set={v => s("gender",     v)}>{GENDERS.map(g     => <option key={g} value={g}>{g}</option>)}</Se></F>
      <F label="Phone"                 err={e.phone}    ><In v={d.phone}     set={v => s("phone",     v)} ph="+91 98765 43210"     err={!!e.phone}     /></F>
      <F label="Alternate Phone"  opt              ><In v={d.altPhone}  set={v => s("altPhone",  v)} ph="Optional"                                   /></F>
      <F label="PAN Number"            err={e.pan}      ><In v={d.pan}       set={v => s("pan",       v.toUpperCase())} ph="ABCDE1234F"  err={!!e.pan}  /></F>
      <F label="Aadhaar Number"        err={e.aadhaar}  ><In v={d.aadhaar}   set={v => s("aadhaar",   v)} ph="XXXX-XXXX-1234"    err={!!e.aadhaar}   /></F>
      <F label="Marital Status"   opt><Se v={d.marital}    set={v => s("marital",    v)}>{MARITAL_OPTS.map(m  => <option key={m} value={m}>{m}</option>)}</Se></F>
      <F label="Blood Group"      opt><Se v={d.bloodGroup} set={v => s("bloodGroup", v)}>{BLOOD_GROUPS.map(b  => <option key={b} value={b}>{b}</option>)}</Se></F>
      <F label="Emergency Contact Name"  err={e.ecName} ><In v={d.ecName}   set={v => s("ecName",   v)} ph="e.g. Ramesh Sharma"  err={!!e.ecName}   /></F>
      <F label="Emergency Contact Phone" err={e.ecPhone}><In v={d.ecPhone}  set={v => s("ecPhone",  v)} ph="+91 98765 55555"     err={!!e.ecPhone}  /></F>
    </div>
  );
}

function Step2({ d, s, e }: { d: FormData["employment"]; s: (k: keyof FormData["employment"], v: string) => void; e: Record<string, string | undefined> }) {
  return (
    <div className="space-y-0">
      <Divider icon="ti-building" title="Role & Department" />
      <div className="grid grid-cols-2 gap-3">
        <F label="Department"      ><Se v={d.department}       set={v => s("department",       v)}>{DEPARTMENT_OPTIONS.map(x => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Designation"      err={e.designation}        ><In v={d.designation}  set={v => s("designation", v)} ph="e.g. Software Engineer" err={!!e.designation} /></F>
        <F label="Branch / Location"><Se v={d.branch}          set={v => s("branch",           v)}>{BRANCHES.map(x        => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Reporting Manager" opt                        ><In v={d.reportingManager} set={v => s("reportingManager", v)} ph="e.g. Meena Iyer" /></F>
        <F label="Employee Type"    ><Se v={d.employeeType}     set={v => s("employeeType",     v)}>{EMP_TYPES.map(x       => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Employment Status"><Se v={d.employmentStatus} set={v => s("employmentStatus", v)}>{EMP_STATUSES.map(x    => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Date of Joining"  err={e.dateOfJoining}      ><In v={d.dateOfJoining} set={v => s("dateOfJoining", v)} type="date" err={!!e.dateOfJoining} /></F>
        <F label="Employee Category"><Se v={d.employeeCategory} set={v => s("employeeCategory", v)}>{CATEGORIES.map(x     => <option key={x} value={x}>{x}</option>)}</Se></F>
      </div>
      <Divider icon="ti-clock" title="Work Schedule" />
      <div className="grid grid-cols-2 gap-3">
        <F label="Shift"               ><Se v={d.shift}           set={v => s("shift",           v)}>{SHIFTS.map(x         => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Work Type"           ><Se v={d.workType}        set={v => s("workType",        v)}>{WORK_TYPES.map(x     => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Weekly Working Days" ><Se v={d.weeklyDays}      set={v => s("weeklyDays",      v)}>{WEEKLY_DAYS.map(x    => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Work Entry Source"   ><Se v={d.workEntrySource} set={v => s("workEntrySource", v)}>{ENTRY_SOURCES.map(x  => <option key={x} value={x}>{x}</option>)}</Se></F>
      </div>
    </div>
  );
}

function Step3({ d, sa, e }: { d: FormData["address"]; sa: (k: keyof FormData["address"], v: string | boolean) => void; e: Record<string, string | undefined> }) {
  function sync(checked: boolean) {
    sa("sameAsCurrent", checked);
    if (checked) { sa("pStreet", d.street); sa("pCity", d.city); sa("pPin", d.pin); sa("pState", d.state); sa("pCountry", d.country); }
  }
  return (
    <div>
      <Divider icon="ti-current-location" title="Current Address" />
      <div className="grid grid-cols-2 gap-3">
        <F label="Street Address" full err={e.street}><In v={d.street} set={v => sa("street", v)} ph="42, 3rd Cross, Indiranagar" err={!!e.street} /></F>
        <F label="City"     err={e.city}><In v={d.city} set={v => sa("city", v)} ph="Bengaluru"  err={!!e.city} /></F>
        <F label="PIN Code" err={e.pin} ><In v={d.pin}  set={v => sa("pin",  v)} ph="560038"     err={!!e.pin}  /></F>
        <F label="State"    ><Se v={d.state}   set={v => sa("state",   v)}>{INDIA_STATES.map(x => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Country" opt><In v={d.country} set={v => sa("country", v)} ph="India" /></F>
      </div>
      <Divider icon="ti-home" title="Permanent Address" />
      <label className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-[var(--outline-v)] bg-[var(--bg-low)] cursor-pointer mb-3">
        <input type="checkbox" checked={d.sameAsCurrent} onChange={ev => sync(ev.target.checked)} suppressHydrationWarning className="w-4 h-4 cursor-pointer" style={{ accentColor: "var(--primary)" }} />
        <span className="text-[13px] text-[var(--on-bg)] font-medium">Same as current address</span>
      </label>
      {!d.sameAsCurrent && (
        <div className="grid grid-cols-2 gap-3">
          <F label="Street Address" full opt><In v={d.pStreet} set={v => sa("pStreet", v)} ph="Street address" /></F>
          <F label="City"    opt><In v={d.pCity} set={v => sa("pCity", v)} ph="City"    /></F>
          <F label="PIN Code" opt><In v={d.pPin}  set={v => sa("pPin",  v)} ph="PIN Code"/></F>
          <F label="State"    opt><Se v={d.pState} set={v => sa("pState", v)}>{INDIA_STATES.map(x => <option key={x} value={x}>{x}</option>)}</Se></F>
          <F label="Country"  opt><In v={d.pCountry} set={v => sa("pCountry", v)} ph="India" /></F>
        </div>
      )}
    </div>
  );
}

function Step4({ d, s }: { d: FormData["education"]; s: (k: keyof FormData["education"], v: string) => void }) {
  return (
    <div>
      <Divider icon="ti-certificate" title="Highest Qualification" />
      <div className="grid grid-cols-2 gap-3">
        <F label="Degree"            ><Se v={d.degree}        set={v => s("degree",        v)}>{DEGREES.map(x => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Specialisation" opt><In v={d.specialisation} set={v => s("specialisation", v)} ph="e.g. Computer Science" /></F>
        <F label="University / Institution" opt><In v={d.university}    set={v => s("university",    v)} ph="e.g. VTU, Belgaum" /></F>
        <F label="Year of Passing"          opt><In v={d.yearOfPassing} set={v => s("yearOfPassing", v)} ph="e.g. 2019" /></F>
        <F label="CGPA / Percentage"        opt><In v={d.cgpa}          set={v => s("cgpa",          v)} ph="e.g. 8.4 CGPA" /></F>
        <F label="Mode"                     opt><Se v={d.mode}          set={v => s("mode",          v)}>{MODES.map(x => <option key={x} value={x}>{x}</option>)}</Se></F>
      </div>
      <Divider icon="ti-briefcase" title="Most Recent Work Experience" />
      <div className="grid grid-cols-2 gap-3">
        <F label="Previous Employer"  opt><In v={d.prevEmployer}   set={v => s("prevEmployer",   v)} ph="e.g. Infosys Ltd"       /></F>
        <F label="Designation"        opt><In v={d.prevDesignation} set={v => s("prevDesignation",v)} ph="e.g. Systems Engineer"  /></F>
        <F label="From Date"          opt><In v={d.fromDate}        set={v => s("fromDate",        v)} type="date"                /></F>
        <F label="To Date"            opt><In v={d.toDate}          set={v => s("toDate",          v)} type="date"                /></F>
        <F label="Reason for Leaving" opt full><In v={d.reasonLeaving} set={v => s("reasonLeaving", v)} ph="e.g. Career growth"  /></F>
      </div>
    </div>
  );
}

const DOC_LIST: { key: DocKey; label: string; required: boolean }[] = [
  { key: "aadhaar",    label: "Aadhaar Card",                 required: true  },
  { key: "pan",        label: "PAN Card",                     required: true  },
  { key: "degree",     label: "Degree Certificate",           required: true  },
  { key: "experience", label: "Experience / Relieving Letter",required: false },
  { key: "offer",      label: "Signed Offer Letter",          required: true  },
  { key: "photo",      label: "Passport-size Photograph",     required: true  },
];

function Step5({ d, toggle }: { d: FormData["docs"]; toggle: (k: DocKey) => void }) {
  const count = Object.values(d).filter(Boolean).length;
  return (
    <div className="space-y-2.5">
      <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg" style={{ background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.18)" }}>
        <i className="ti ti-info-circle text-[14px] mt-0.5 flex-shrink-0" style={{ color: "var(--primary)" }} />
        <p className="text-[12.5px]" style={{ color: "var(--primary)" }}>Upload clear scans. Accepted: PDF, JPG, PNG (max 5MB each).</p>
      </div>
      {DOC_LIST.map(doc => (
        <div key={doc.key} className="flex items-center justify-between px-4 py-3 rounded-lg border border-[var(--outline-v)] bg-white hover:border-[var(--primary)] transition-colors">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: d[doc.key] ? "rgba(22,163,74,0.10)" : "rgba(30,78,140,0.08)" }}>
              <i className={`ti ${d[doc.key] ? "ti-file-check" : "ti-file-text"} text-[15px]`} style={{ color: d[doc.key] ? "var(--success)" : "var(--primary)" }} />
            </div>
            <div>
              <p className="text-[13px] font-medium text-[var(--on-bg)]">
                {doc.label}
                {!doc.required && <span className="ml-1.5 text-[11px] font-normal text-[var(--on-variant)]">(Optional)</span>}
                {doc.required  && <span className="ml-0.5 font-bold" style={{ color: "var(--error)" }}>*</span>}
              </p>
              <p className="text-[11.5px] text-[var(--on-variant)]">{d[doc.key] ? "Uploaded successfully" : "Not yet uploaded"}</p>
            </div>
          </div>
          <button onClick={() => toggle(doc.key)} suppressHydrationWarning
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors ${d[doc.key] ? "border-[var(--success)] text-[var(--success)]" : "border-[var(--primary)] text-[var(--primary)] hover:bg-[rgba(30,78,140,0.05)]"}`}>
            <i className={`ti ${d[doc.key] ? "ti-check" : "ti-upload"} text-[13px]`} />
            {d[doc.key] ? "Uploaded" : "Upload"}
          </button>
        </div>
      ))}
      <p className="text-[11.5px] text-[var(--on-variant)] text-right pt-1">{count} of {DOC_LIST.length} documents uploaded</p>
    </div>
  );
}

function Step6({ d, s, e }: { d: FormData["bank"]; s: (k: keyof FormData["bank"], v: string) => void; e: Record<string, string | undefined> }) {
  return (
    <div className="space-y-0">
      <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg mb-3" style={{ background: "rgba(217,119,6,0.07)", border: "1px solid rgba(217,119,6,0.25)" }}>
        <i className="ti ti-alert-triangle text-[14px] mt-0.5 flex-shrink-0" style={{ color: "#b45309" }} />
        <p className="text-[12.5px]" style={{ color: "#92400e" }}>Please ensure your bank details are accurate. Incorrect details may delay salary credit.</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <F label="Bank Name"            ><Se v={d.bankName}      set={v => s("bankName",      v)}>{BANKS.map(x         => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Account Holder Name" err={e.accountHolder}  ><In v={d.accountHolder}  set={v => s("accountHolder",  v)} ph="As per bank records"     err={!!e.accountHolder}  /></F>
        <F label="Account Number"      err={e.accountNumber}  ><In v={d.accountNumber}  set={v => s("accountNumber",  v)} ph="e.g. 123456789012"        err={!!e.accountNumber}  /></F>
        <F label="Confirm Account Number" err={e.confirmAccount}><In v={d.confirmAccount} set={v => s("confirmAccount", v)} ph="Re-enter account number" err={!!e.confirmAccount} /></F>
        <F label="IFSC Code"           err={e.ifsc}           ><In v={d.ifsc}           set={v => s("ifsc",           v.toUpperCase())} ph="HDFC0001234" err={!!e.ifsc}           /></F>
        <F label="Account Type"        ><Se v={d.accountType}   set={v => s("accountType",   v)}>{ACCOUNT_TYPES.map(x  => <option key={x} value={x}>{x}</option>)}</Se></F>
        <F label="Branch Name"     opt ><In v={d.branchName}    set={v => s("branchName",    v)} ph="e.g. Indiranagar" /></F>
        <F label="UAN (if existing)" opt><In v={d.uan}          set={v => s("uan",           v)} ph="Optional"         /></F>
      </div>
    </div>
  );
}

function ReviewSection({ title, icon, onEdit, rows }: { title: string; icon: string; onEdit: () => void; rows: { label: string; value: string }[] }) {
  return (
    <div className="rounded-xl border border-[var(--outline-v)] overflow-hidden mb-3">
      <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-low)] border-b border-[var(--outline-v)]">
        <div className="flex items-center gap-2">
          <i className={`ti ${icon} text-[13px]`} style={{ color: "var(--primary)" }} />
          <span className="text-[12.5px] font-semibold text-[var(--on-bg)]">{title}</span>
        </div>
        <button onClick={onEdit} suppressHydrationWarning className="flex items-center gap-1 text-[11.5px] font-medium px-2.5 py-1 rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] hover:text-[var(--primary)] hover:border-[var(--primary)] bg-white transition-colors">
          <i className="ti ti-pencil text-[12px]" /> Edit
        </button>
      </div>
      <div className="px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-2">
        {rows.map(r => (
          <div key={r.label}>
            <p className="text-[10.5px] text-[var(--on-variant)] font-medium">{r.label}</p>
            <p className="text-[12.5px] text-[var(--on-bg)] font-medium mt-0.5">{r.value || "—"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Step7({ form, goTo, declaration, setDeclaration, declErr }: {
  form: FormData; goTo: (s: number) => void;
  declaration: boolean; setDeclaration: (v: boolean) => void; declErr?: string;
}) {
  const p = form.personal, em = form.employment, a = form.address, ed = form.education, b = form.bank;
  const uploaded = Object.values(form.docs).filter(Boolean).length;
  return (
    <div>
      <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg mb-4" style={{ background: "rgba(22,163,74,0.07)", border: "1px solid rgba(22,163,74,0.22)" }}>
        <i className="ti ti-circle-check text-[14px] mt-0.5 flex-shrink-0" style={{ color: "var(--success)" }} />
        <p className="text-[12.5px] font-medium" style={{ color: "#15803d" }}>Almost done! Please review all the details below. You won&apos;t be able to edit after submission until HR reviews and approves.</p>
      </div>
      <ReviewSection title="Personal Information" icon="ti-user"          onEdit={() => goTo(1)} rows={[{ label:"Full Name", value:`${p.firstName} ${p.lastName}`.trim() }, { label:"Date of Birth", value:p.dob }, { label:"Gender", value:p.gender }, { label:"Phone", value:p.phone }, { label:"PAN", value:p.pan }, { label:"Aadhaar", value:p.aadhaar }, { label:"Emergency Contact", value:`${p.ecName} ${p.ecPhone}`.trim() }, { label:"Marital Status", value:p.marital }]} />
      <ReviewSection title="Employment Details"   icon="ti-id"            onEdit={() => goTo(2)} rows={[{ label:"Department", value:em.department }, { label:"Designation", value:em.designation }, { label:"Branch", value:em.branch }, { label:"Employee Type", value:em.employeeType }, { label:"Date of Joining", value:em.dateOfJoining }, { label:"Shift", value:em.shift }, { label:"Work Type", value:em.workType }, { label:"Weekly Days", value:em.weeklyDays }]} />
      <ReviewSection title="Address"              icon="ti-map-pin"       onEdit={() => goTo(3)} rows={[{ label:"Street", value:a.street }, { label:"City", value:a.city }, { label:"PIN Code", value:a.pin }, { label:"State", value:a.state }]} />
      <ReviewSection title="Education"            icon="ti-school"        onEdit={() => goTo(4)} rows={[{ label:"Degree", value:ed.degree }, { label:"Specialisation", value:ed.specialisation }, { label:"University", value:ed.university }, { label:"Previous Employer", value:ed.prevEmployer }]} />
      <ReviewSection title="Documents"            icon="ti-file"          onEdit={() => goTo(5)} rows={[{ label:"Uploaded", value:`${uploaded} of ${DOC_LIST.length}` }, { label:"Status", value: uploaded >= 5 ? "All required uploaded" : "Some pending" }]} />
      <ReviewSection title="Bank Details"         icon="ti-building-bank" onEdit={() => goTo(6)} rows={[{ label:"Bank", value:b.bankName }, { label:"Account Holder", value:b.accountHolder }, { label:"Account Number", value: b.accountNumber ? "••••••" + b.accountNumber.slice(-4) : "" }, { label:"IFSC", value:b.ifsc }]} />
      <label className="flex items-start gap-3 p-3.5 rounded-xl border border-[var(--outline-v)] bg-[var(--bg-low)] cursor-pointer mt-3">
        <input type="checkbox" checked={declaration} onChange={ev => setDeclaration(ev.target.checked)} suppressHydrationWarning className="w-4 h-4 mt-0.5 flex-shrink-0 cursor-pointer" style={{ accentColor: "var(--primary)" }} />
        <span className="text-[12.5px] text-[var(--on-bg)] leading-relaxed">I confirm that all details provided are accurate. I understand that providing false information may lead to termination of employment.</span>
      </label>
      {declErr && <p className="text-[11.5px] mt-2 font-medium" style={{ color: "var(--error)" }}><i className="ti ti-alert-circle mr-1" />{declErr}</p>}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   VALIDATION
══════════════════════════════════════════════════════════════ */
function validate(step: number, form: FormData): Record<string, string> {
  const e: Record<string, string> = {};
  if (step === 1) {
    const p = form.personal;
    if (!p.firstName.trim()) e.firstName = "Required";
    if (!p.lastName.trim())  e.lastName  = "Required";
    if (!p.dob)              e.dob       = "Required";
    if (!p.phone.trim())     e.phone     = "Required";
    if (!p.pan.trim())       e.pan       = "Required";
    if (!p.aadhaar.trim())   e.aadhaar   = "Required";
    if (!p.ecName.trim())    e.ecName    = "Required";
    if (!p.ecPhone.trim())   e.ecPhone   = "Required";
  }
  if (step === 2) {
    if (!form.employment.designation.trim())  e.designation   = "Required";
    if (!form.employment.dateOfJoining)       e.dateOfJoining = "Required";
  }
  if (step === 3) {
    if (!form.address.street.trim()) e.street = "Required";
    if (!form.address.city.trim())   e.city   = "Required";
    if (!form.address.pin.trim())    e.pin    = "Required";
  }
  if (step === 6) {
    if (!form.bank.accountHolder.trim())  e.accountHolder  = "Required";
    if (!form.bank.accountNumber.trim())  e.accountNumber  = "Required";
    if (!form.bank.ifsc.trim())           e.ifsc           = "Required";
    if (form.bank.accountNumber && form.bank.confirmAccount && form.bank.accountNumber !== form.bank.confirmAccount)
      e.confirmAccount = "Account numbers do not match";
  }
  return e;
}

/* ══════════════════════════════════════════════════════════════
   MAIN MODAL
══════════════════════════════════════════════════════════════ */
export default function AddEmployeeWizard({
  onClose,
  onCreate,
  existingCount,
}: {
  onClose: () => void;
  onCreate: (e: Employee) => void;
  existingCount: number;
}) {
  const [step, setStep]   = useState(1);
  const [form, setForm]   = useState<FormData>(EMPTY);
  const [errs, setErrs]   = useState<Record<string, string | undefined>>({});
  const [declErr, setDeclErr] = useState("");
  const [done, setDone]   = useState(false);

  const p           = form.personal;
  const displayName = [p.firstName, p.lastName].filter(Boolean).join(" ") || "New Employee";
  const displayRole = [form.employment.designation, form.employment.department].filter(Boolean).join(" • ") || "—";
  const initials    = [p.firstName[0], p.lastName[0]].filter(Boolean).join("").toUpperCase() || "NE";
  const pct         = Math.round(((step - 1) / TOTAL) * 100);
  const currentStep = STEPS[step - 1];

  /* setters */
  function sp(k: keyof FormData["personal"],   v: string) { setForm(f => ({ ...f, personal:   { ...f.personal,   [k]: v } })); setErrs(e => ({ ...e, [k]: undefined })); }
  function se(k: keyof FormData["employment"], v: string) { setForm(f => ({ ...f, employment: { ...f.employment, [k]: v } })); setErrs(e => ({ ...e, [k]: undefined })); }
  function sa(k: keyof FormData["address"],    v: string | boolean) { setForm(f => ({ ...f, address: { ...f.address, [k]: v } })); setErrs(e => ({ ...e, [k]: undefined })); }
  function sed(k: keyof FormData["education"], v: string) { setForm(f => ({ ...f, education: { ...f.education, [k]: v } })); }
  function sb(k: keyof FormData["bank"],       v: string) { setForm(f => ({ ...f, bank: { ...f.bank, [k]: v } })); setErrs(e => ({ ...e, [k]: undefined })); }
  function toggleDoc(k: DocKey) { setForm(f => ({ ...f, docs: { ...f.docs, [k]: !f.docs[k] } })); }
  function goTo(s: number)  { setErrs({}); setDeclErr(""); setStep(s); }

  function next() {
    const errors = validate(step, form);
    if (Object.keys(errors).length) { setErrs(errors); return; }
    setErrs({});
    if (step < TOTAL) setStep(s => s + 1);
  }
  function prev() { setErrs({}); setDeclErr(""); if (step > 1) setStep(s => s - 1); }

  function submit() {
    if (!form.declaration) { setDeclErr("Please accept the declaration to proceed."); return; }
    const code = `RSS${String(existingCount + 1).padStart(5, "0")}D`;
    const { sameAsCurrent: _sc, ...addrFields } = form.address;
    const emp: Employee = {
      id: code, code,
      firstName:     p.firstName.trim(),
      middleName:    "",
      lastName:      p.lastName.trim(),
      email:         `${p.firstName.toLowerCase()}.${p.lastName.toLowerCase()}@royal.com`,
      phone:         p.phone.trim(),
      department:    form.employment.department,
      designation:   form.employment.designation.trim(),
      dateOfJoining: form.employment.dateOfJoining,
      dateOfBirth:   p.dob,
      location:      form.employment.branch,
      gender:        p.gender.toLowerCase() as Gender,
      status:        "onboarding" as EmployeeStatus,
      details:       { ...p, ...form.employment, ...addrFields, ...form.education, ...form.bank, code },
      tables:        {},
    };
    addEmployee(emp);
    onCreate(emp);
    setDone(true);
  }

  return (
    /* Full-screen overlay — z-[300] sits above sidebar (z-[100]) */
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center p-4"
      style={{ background: "rgba(10,20,40,0.55)", backdropFilter: "blur(8px)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-[var(--bg)] rounded-2xl shadow-2xl flex flex-col w-full"
        style={{ maxWidth: 700, maxHeight: "93vh" }}
      >
        {/* ── Success screen ───────────────────────────────── */}
        {done ? (
          <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mb-5" style={{ background: "rgba(22,163,74,0.12)" }}>
              <i className="ti ti-circle-check text-[44px]" style={{ color: "var(--success)" }} />
            </div>
            <h2 className="text-[20px] font-bold text-[var(--on-bg)] mb-2">Employee Added Successfully!</h2>
            <p className="text-[13.5px] text-[var(--on-variant)] mb-8 max-w-sm">{displayName} has been added. HR team will review and activate the account.</p>
            <button onClick={onClose} suppressHydrationWarning
              className="flex items-center gap-2 px-6 py-3 rounded-xl text-[13.5px] font-semibold text-white shadow-md"
              style={{ background: "var(--primary)" }}>
              <i className="ti ti-check text-[15px]" /> Done
            </button>
          </div>
        ) : (
          <>
            {/* ── Scrollable body ───────────────────────────── */}
            <div className="flex-1 overflow-y-auto">

              {/* Welcome card */}
              <div className="bg-white border-b border-[var(--outline-v)] px-5 py-4 flex items-center gap-4 sticky top-0 z-10">
                <div className="w-11 h-11 rounded-full flex items-center justify-center text-[14px] font-bold text-white flex-shrink-0" style={{ background: "var(--primary)" }}>
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[15px] font-bold text-[var(--on-bg)] leading-tight">Welcome, {displayName}</p>
                  <p className="text-[12px] text-[var(--on-variant)] truncate mt-0.5">{displayRole} · Royal Staffing Services LLP</p>
                </div>
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11.5px] font-semibold flex-shrink-0" style={{ background: "rgba(22,163,74,0.10)", color: "var(--success)" }}>
                  <i className="ti ti-check text-[11px]" /> Onboarding
                </span>
                <button onClick={onClose} suppressHydrationWarning
                  className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--on-variant)] hover:bg-[var(--bg-low)] transition-colors ml-1 flex-shrink-0">
                  <i className="ti ti-x text-[18px]" />
                </button>
              </div>

              {/* Step indicator */}
              <div className="bg-white border-b border-[var(--outline-v)] px-4 py-3">
                <div className="flex items-center justify-between gap-0.5 overflow-x-auto">
                  {STEPS.map((s, idx) => {
                    const done  = step > s.id;
                    const active = step === s.id;
                    return (
                      <div key={s.id} className="flex items-center flex-shrink-0">
                        {idx > 0 && (
                          <div className="w-5 h-0.5 mx-0.5 rounded-full" style={{ background: done ? "var(--primary)" : "var(--outline-v)" }} />
                        )}
                        <button onClick={() => done && goTo(s.id)} suppressHydrationWarning
                          className={`flex flex-col items-center gap-1 ${done ? "cursor-pointer" : "cursor-default"}`}
                          style={{ opacity: step < s.id ? 0.45 : 1 }}>
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold border-2 transition-all`}
                            style={done ? { background: "var(--primary)", borderColor: "var(--primary)", color: "#fff" }
                              : active ? { background: "#fff", borderColor: "var(--primary)", color: "var(--primary)" }
                              : { background: "#fff", borderColor: "var(--outline-v)", color: "var(--on-variant)" }}>
                            {done ? <i className="ti ti-check text-[12px]" /> : s.id}
                          </div>
                          <div style={{ minWidth: 40 }} className="text-center">
                            <p className="text-[8.5px] font-semibold uppercase tracking-wide text-[var(--on-variant)]">STEP {s.id}</p>
                            <p className={`text-[9.5px] font-medium ${active ? "text-[var(--primary)]" : "text-[var(--on-variant)]"}`}>{s.short}</p>
                          </div>
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Form card */}
              <div className="bg-white m-4 rounded-xl border border-[var(--outline-v)]">
                {/* Section header */}
                <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--outline-v)]">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: "rgba(30,78,140,0.10)" }}>
                    <i className={`ti ${currentStep.icon} text-[18px]`} style={{ color: "var(--primary)" }} />
                  </div>
                  <div>
                    <h2 className="text-[15px] font-bold text-[var(--on-bg)]">{currentStep.label}</h2>
                    <p className="text-[12px] text-[var(--on-variant)] mt-0.5">{currentStep.sub}</p>
                  </div>
                </div>

                {/* Form fields */}
                <div className="px-5 py-5">
                  {step === 1 && <Step1 d={form.personal}   s={sp}  e={errs} />}
                  {step === 2 && <Step2 d={form.employment} s={se}  e={errs} />}
                  {step === 3 && <Step3 d={form.address}    sa={sa} e={errs} />}
                  {step === 4 && <Step4 d={form.education}  s={sed} />}
                  {step === 5 && <Step5 d={form.docs}       toggle={toggleDoc} />}
                  {step === 6 && <Step6 d={form.bank}       s={sb}  e={errs} />}
                  {step === 7 && <Step7 form={form} goTo={goTo} declaration={form.declaration} setDeclaration={v => setForm(f => ({ ...f, declaration: v }))} declErr={declErr} />}
                </div>
              </div>
            </div>

            {/* ── Sticky footer nav ───────────────────────── */}
            <div className="flex items-center justify-between px-5 py-3.5 border-t border-[var(--outline-v)] bg-white rounded-b-2xl flex-shrink-0">
              <button onClick={prev} disabled={step === 1} suppressHydrationWarning
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium border border-[var(--outline-v)] text-[var(--on-bg)] bg-white hover:bg-[var(--bg-low)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                <i className="ti ti-arrow-left text-[13px]" /> Previous
              </button>
              <span className="text-[12px] text-[var(--on-variant)] font-medium">
                Step {step} of {TOTAL} · {pct}% complete
              </span>
              {step < TOTAL ? (
                <button onClick={next} suppressHydrationWarning
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg text-[13px] font-semibold text-white transition-colors shadow-sm"
                  style={{ background: "var(--primary)" }}>
                  Continue <i className="ti ti-arrow-right text-[13px]" />
                </button>
              ) : (
                <button onClick={submit} suppressHydrationWarning
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg text-[13px] font-semibold text-white transition-colors shadow-sm"
                  style={{ background: "var(--success)" }}>
                  <i className="ti ti-send text-[13px]" /> Submit to HR
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
