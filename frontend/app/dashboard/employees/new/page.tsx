"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { DEPARTMENT_OPTIONS } from "../_data";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/useCurrentUser";

/* ══════════════════════════════════════════════════════════════
   CONSTANTS & OPTIONS
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

const GENDERS         = ["Male", "Female", "Transgender"];
const BLOOD_GROUPS    = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const MARITAL_OPTS    = ["Single", "Married", "Divorced", "Widowed"];
const EMP_TYPES       = ["Permanent", "Contract", "Intern", "Probation"];
const EMP_STATUSES    = ["Probation", "Confirmed", "Active", "On Notice"];
const SHIFTS          = ["General (9-6)", "Morning (6-2)", "Evening (2-10)", "Night (10-6)"];
const WORK_TYPES      = ["Office", "WFH", "Hybrid"];
const ENTRY_SOURCES   = ["Biometric", "Mobile App", "Web Portal", "Manual"];
const WEEKLY_DAYS     = ["5 Days (Mon–Fri)", "5.5 Days", "6 Days (Mon–Sat)"];
const CATEGORIES      = ["General", "OBC", "SC", "ST", "EWS"];
const DEGREES         = ["Bachelor of Engineering", "Bachelor of Science", "Bachelor of Commerce", "Master of Technology", "MBA", "PhD", "Diploma", "12th / HSC", "10th / SSC"];
const MODES           = ["Full-time", "Part-time", "Distance", "Online"];
const BANKS           = ["HDFC Bank", "SBI", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "Bank of Baroda", "Punjab National Bank", "Canara Bank"];
const ACCOUNT_TYPES   = ["Savings", "Current", "Salary"];
const BRANCHES        = ["Head Office", "Bengaluru Branch", "Mumbai Branch", "Delhi Branch", "Chennai Branch", "Hyderabad Branch", "Pune Branch"];
const INDIA_STATES    = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana",
  "Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur",
  "Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana",
  "Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Jammu & Kashmir","Ladakh",
  "Chandigarh","Puducherry","Andaman & Nicobar Islands","Lakshadweep",
];

/* ══════════════════════════════════════════════════════════════
   FORM STATE TYPES
══════════════════════════════════════════════════════════════ */
type DocKey = "aadhaar" | "pan" | "degree" | "experience" | "offer" | "photo";

interface FormData {
  personal: {
    firstName: string; lastName: string; email: string; dob: string; gender: string;
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
  personal: {
    firstName: "", lastName: "", email: "", dob: "", gender: "Male",
    phone: "", altPhone: "", pan: "", aadhaar: "",
    marital: "Single", bloodGroup: "B+", ecName: "", ecPhone: "",
  },
  employment: {
    department: DEPARTMENT_OPTIONS[0] ?? "Engineering",
    designation: "", branch: "Head Office",
    reportingManager: "", employeeType: "Permanent", employmentStatus: "Probation",
    dateOfJoining: "", shift: "General (9-6)", workType: "Office",
    workEntrySource: "Biometric", weeklyDays: "5 Days (Mon–Fri)", employeeCategory: "General",
  },
  address: {
    street: "", city: "", pin: "", state: "Karnataka", country: "India",
    sameAsCurrent: false,
    pStreet: "", pCity: "", pPin: "", pState: "Karnataka", pCountry: "India",
  },
  education: {
    degree: "Bachelor of Engineering", specialisation: "", university: "",
    yearOfPassing: "", cgpa: "", mode: "Full-time",
    prevEmployer: "", prevDesignation: "", fromDate: "", toDate: "", reasonLeaving: "",
  },
  docs: { aadhaar: false, pan: false, degree: false, experience: false, offer: false, photo: false },
  bank: {
    bankName: "HDFC Bank", accountHolder: "", accountNumber: "",
    confirmAccount: "", ifsc: "", accountType: "Savings",
    branchName: "", uan: "",
  },
  declaration: false,
};

/* ══════════════════════════════════════════════════════════════
   SHARED STYLE TOKENS
══════════════════════════════════════════════════════════════ */
const INP = [
  "w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)]",
  "text-[13px] bg-white text-[var(--on-bg)] placeholder:text-[#a5b0c2]",
  "focus:outline-none focus:border-[var(--primary)] focus:ring-2",
  "focus:ring-[rgba(30,78,140,0.12)] transition-colors",
].join(" ");
const INP_ERR = INP.replace("border-[var(--outline-v)]", "border-[var(--error)]");
const SEL = INP + " appearance-none pr-9 cursor-pointer";
const SEL_STYLE = {
  backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>\")",
  backgroundRepeat: "no-repeat" as const,
  backgroundPosition: "right 10px center" as const,
  backgroundSize: "15px" as const,
};

/* ══════════════════════════════════════════════════════════════
   TINY HELPERS
══════════════════════════════════════════════════════════════ */
function Lbl({ children, opt }: { children: ReactNode; opt?: boolean }) {
  return (
    <label className={`block text-[12.5px] font-${opt ? "medium text-[var(--on-variant)]" : "semibold text-[var(--on-bg)]"} mb-1.5`}>
      {children}{!opt && <span className="ml-0.5 font-bold" style={{ color: "var(--error)" }}>*</span>}
    </label>
  );
}

function F({ label, opt, err, children }: { label: string; opt?: boolean; err?: string; children: ReactNode }) {
  return (
    <div>
      <Lbl opt={opt}>{label}</Lbl>
      {children}
      {err && <p className="text-[11.5px] mt-1 font-medium" style={{ color: "var(--error)" }}>{err}</p>}
    </div>
  );
}

function Sel({ value, onChange, children }: { value: string; onChange: (v: string) => void; children: ReactNode }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} className={SEL} style={SEL_STYLE} suppressHydrationWarning>
      {children}
    </select>
  );
}

function Row({ children, half }: { children: ReactNode; half?: boolean }) {
  return (
    <div className={`grid gap-4 ${half ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2"}`}>
      {children}
    </div>
  );
}

function SubHdr({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 mt-5 mb-4 pb-2 border-b border-[var(--outline-v)]">
      <i className={`ti ${icon} text-[14px]`} style={{ color: "var(--primary)" }} />
      <span className="text-[12.5px] font-bold uppercase tracking-wide" style={{ color: "var(--primary)" }}>{title}</span>
    </div>
  );
}

function Inp({ value, onChange, placeholder, type = "text", err }: {
  value: string; onChange: (v: string) => void; placeholder?: string; type?: string; err?: boolean;
}) {
  return (
    <input type={type} value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} suppressHydrationWarning
      className={err ? INP_ERR : INP} />
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 1 — Personal Information
══════════════════════════════════════════════════════════════ */
function StepPersonal({ d, set, errs }: {
  d: FormData["personal"];
  set: (k: keyof FormData["personal"], v: string) => void;
  errs: Partial<Record<keyof FormData["personal"], string>>;
}) {
  return (
    <div className="space-y-4">
      <Row>
        <F label="First Name" err={errs.firstName}>
          <Inp value={d.firstName} onChange={v => set("firstName", v)} placeholder="e.g. Priya" err={!!errs.firstName} />
        </F>
        <F label="Last Name" err={errs.lastName}>
          <Inp value={d.lastName} onChange={v => set("lastName", v)} placeholder="e.g. Sharma" err={!!errs.lastName} />
        </F>
      </Row>
      <Row half>
        <F label="Work Email" err={errs.email}>
          <Inp type="email" value={d.email} onChange={v => set("email", v)} placeholder="e.g. priya.sharma@company.com" err={!!errs.email} />
        </F>
      </Row>
      <Row>
        <F label="Date of Birth" err={errs.dob}>
          <Inp type="date" value={d.dob} onChange={v => set("dob", v)} err={!!errs.dob} />
        </F>
        <F label="Gender">
          <Sel value={d.gender} onChange={v => set("gender", v)}>
            {GENDERS.map(g => <option key={g} value={g}>{g}</option>)}
          </Sel>
        </F>
      </Row>
      <Row>
        <F label="Phone" err={errs.phone}>
          <Inp type="tel" value={d.phone} onChange={v => set("phone", v)} placeholder="+91 98765 43210" err={!!errs.phone} />
        </F>
        <F label="Alternate Phone" opt>
          <Inp type="tel" value={d.altPhone} onChange={v => set("altPhone", v)} placeholder="Optional" />
        </F>
      </Row>
      <Row>
        <F label="PAN Number" err={errs.pan}>
          <Inp value={d.pan} onChange={v => set("pan", v.toUpperCase())} placeholder="ABCDE1234F" err={!!errs.pan} />
        </F>
        <F label="Aadhaar Number" err={errs.aadhaar}>
          <Inp value={d.aadhaar} onChange={v => set("aadhaar", v)} placeholder="XXXX-XXXX-1234" err={!!errs.aadhaar} />
        </F>
      </Row>
      <Row>
        <F label="Marital Status" opt>
          <Sel value={d.marital} onChange={v => set("marital", v)}>
            {MARITAL_OPTS.map(m => <option key={m} value={m}>{m}</option>)}
          </Sel>
        </F>
        <F label="Blood Group" opt>
          <Sel value={d.bloodGroup} onChange={v => set("bloodGroup", v)}>
            {BLOOD_GROUPS.map(b => <option key={b} value={b}>{b}</option>)}
          </Sel>
        </F>
      </Row>
      <Row>
        <F label="Emergency Contact Name" err={errs.ecName}>
          <Inp value={d.ecName} onChange={v => set("ecName", v)} placeholder="e.g. Ramesh Sharma" err={!!errs.ecName} />
        </F>
        <F label="Emergency Contact Phone" err={errs.ecPhone}>
          <Inp type="tel" value={d.ecPhone} onChange={v => set("ecPhone", v)} placeholder="+91 98765 55555" err={!!errs.ecPhone} />
        </F>
      </Row>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 2 — Employment Details
══════════════════════════════════════════════════════════════ */
function StepEmployment({ d, set, errs }: {
  d: FormData["employment"];
  set: (k: keyof FormData["employment"], v: string) => void;
  errs: Partial<Record<keyof FormData["employment"], string>>;
}) {
  return (
    <div className="space-y-4">
      <SubHdr icon="ti-building" title="Role & Department" />
      <Row>
        <F label="Department" err={errs.department}>
          <Sel value={d.department} onChange={v => set("department", v)}>
            {DEPARTMENT_OPTIONS.map(dep => <option key={dep} value={dep}>{dep}</option>)}
          </Sel>
        </F>
        <F label="Designation" err={errs.designation}>
          <Inp value={d.designation} onChange={v => set("designation", v)} placeholder="e.g. Software Engineer" err={!!errs.designation} />
        </F>
      </Row>
      <Row>
        <F label="Branch / Location">
          <Sel value={d.branch} onChange={v => set("branch", v)}>
            {BRANCHES.map(b => <option key={b} value={b}>{b}</option>)}
          </Sel>
        </F>
        <F label="Reporting Manager" opt>
          <Inp value={d.reportingManager} onChange={v => set("reportingManager", v)} placeholder="e.g. Meena Iyer" />
        </F>
      </Row>
      <Row>
        <F label="Employee Type">
          <Sel value={d.employeeType} onChange={v => set("employeeType", v)}>
            {EMP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </Sel>
        </F>
        <F label="Employment Status">
          <Sel value={d.employmentStatus} onChange={v => set("employmentStatus", v)}>
            {EMP_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </Sel>
        </F>
      </Row>
      <Row>
        <F label="Date of Joining" err={errs.dateOfJoining}>
          <Inp type="date" value={d.dateOfJoining} onChange={v => set("dateOfJoining", v)} err={!!errs.dateOfJoining} />
        </F>
        <F label="Employee Category">
          <Sel value={d.employeeCategory} onChange={v => set("employeeCategory", v)}>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </Sel>
        </F>
      </Row>

      <SubHdr icon="ti-clock" title="Work Schedule" />
      <Row>
        <F label="Shift">
          <Sel value={d.shift} onChange={v => set("shift", v)}>
            {SHIFTS.map(s => <option key={s} value={s}>{s}</option>)}
          </Sel>
        </F>
        <F label="Work Type">
          <Sel value={d.workType} onChange={v => set("workType", v)}>
            {WORK_TYPES.map(w => <option key={w} value={w}>{w}</option>)}
          </Sel>
        </F>
      </Row>
      <Row>
        <F label="Weekly Working Days">
          <Sel value={d.weeklyDays} onChange={v => set("weeklyDays", v)}>
            {WEEKLY_DAYS.map(w => <option key={w} value={w}>{w}</option>)}
          </Sel>
        </F>
        <F label="Work Entry Source">
          <Sel value={d.workEntrySource} onChange={v => set("workEntrySource", v)}>
            {ENTRY_SOURCES.map(e => <option key={e} value={e}>{e}</option>)}
          </Sel>
        </F>
      </Row>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 3 — Address Details
══════════════════════════════════════════════════════════════ */
function StepAddress({ d, setAddr, errs }: {
  d: FormData["address"];
  setAddr: (k: keyof FormData["address"], v: string | boolean) => void;
  errs: Partial<Record<string, string>>;
}) {
  function syncPermanent(checked: boolean) {
    setAddr("sameAsCurrent", checked);
    if (checked) {
      setAddr("pStreet", d.street);
      setAddr("pCity", d.city);
      setAddr("pPin", d.pin);
      setAddr("pState", d.state);
      setAddr("pCountry", d.country);
    }
  }

  return (
    <div className="space-y-4">
      <SubHdr icon="ti-current-location" title="Current Address" />
      <Row half>
        <F label="Street Address" err={errs.street}>
          <Inp value={d.street} onChange={v => setAddr("street", v)} placeholder="42, 3rd Cross, Indiranagar" err={!!errs.street} />
        </F>
      </Row>
      <Row>
        <F label="City" err={errs.city}>
          <Inp value={d.city} onChange={v => setAddr("city", v)} placeholder="Bengaluru" err={!!errs.city} />
        </F>
        <F label="PIN Code" err={errs.pin}>
          <Inp value={d.pin} onChange={v => setAddr("pin", v)} placeholder="560038" err={!!errs.pin} />
        </F>
      </Row>
      <Row>
        <F label="State">
          <Sel value={d.state} onChange={v => setAddr("state", v)}>
            {INDIA_STATES.map(s => <option key={s} value={s}>{s}</option>)}
          </Sel>
        </F>
        <F label="Country">
          <Inp value={d.country} onChange={v => setAddr("country", v)} placeholder="India" />
        </F>
      </Row>

      <SubHdr icon="ti-home" title="Permanent Address" />
      <label className="flex items-center gap-3 px-4 py-3 rounded-lg border border-[var(--outline-v)] bg-[var(--bg-low)] cursor-pointer">
        <input type="checkbox" checked={d.sameAsCurrent} onChange={e => syncPermanent(e.target.checked)}
          suppressHydrationWarning className="w-4 h-4 cursor-pointer" style={{ accentColor: "var(--primary)" }} />
        <span className="text-[13px] text-[var(--on-bg)] font-medium">Same as current address</span>
      </label>

      {!d.sameAsCurrent && (
        <>
          <Row half>
            <F label="Street Address" opt>
              <Inp value={d.pStreet} onChange={v => setAddr("pStreet", v)} placeholder="Street address" />
            </F>
          </Row>
          <Row>
            <F label="City" opt>
              <Inp value={d.pCity} onChange={v => setAddr("pCity", v)} placeholder="City" />
            </F>
            <F label="PIN Code" opt>
              <Inp value={d.pPin} onChange={v => setAddr("pPin", v)} placeholder="PIN Code" />
            </F>
          </Row>
          <Row>
            <F label="State" opt>
              <Sel value={d.pState} onChange={v => setAddr("pState", v)}>
                {INDIA_STATES.map(s => <option key={s} value={s}>{s}</option>)}
              </Sel>
            </F>
            <F label="Country" opt>
              <Inp value={d.pCountry} onChange={v => setAddr("pCountry", v)} placeholder="India" />
            </F>
          </Row>
        </>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 4 — Education & Experience
══════════════════════════════════════════════════════════════ */
function StepEducation({ d, set }: {
  d: FormData["education"];
  set: (k: keyof FormData["education"], v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <SubHdr icon="ti-certificate" title="Highest Qualification" />
      <Row>
        <F label="Degree">
          <Sel value={d.degree} onChange={v => set("degree", v)}>
            {DEGREES.map(deg => <option key={deg} value={deg}>{deg}</option>)}
          </Sel>
        </F>
        <F label="Specialisation">
          <Inp value={d.specialisation} onChange={v => set("specialisation", v)} placeholder="e.g. Computer Science" />
        </F>
      </Row>
      <Row>
        <F label="University / Institution">
          <Inp value={d.university} onChange={v => set("university", v)} placeholder="e.g. VTU, Belgaum" />
        </F>
        <F label="Year of Passing">
          <Inp value={d.yearOfPassing} onChange={v => set("yearOfPassing", v)} placeholder="e.g. 2019" />
        </F>
      </Row>
      <Row>
        <F label="CGPA / Percentage" opt>
          <Inp value={d.cgpa} onChange={v => set("cgpa", v)} placeholder="e.g. 8.4 CGPA" />
        </F>
        <F label="Mode" opt>
          <Sel value={d.mode} onChange={v => set("mode", v)}>
            {MODES.map(m => <option key={m} value={m}>{m}</option>)}
          </Sel>
        </F>
      </Row>

      <SubHdr icon="ti-briefcase" title="Most Recent Work Experience" />
      <Row>
        <F label="Previous Employer" opt>
          <Inp value={d.prevEmployer} onChange={v => set("prevEmployer", v)} placeholder="e.g. Infosys Ltd" />
        </F>
        <F label="Designation" opt>
          <Inp value={d.prevDesignation} onChange={v => set("prevDesignation", v)} placeholder="e.g. Systems Engineer" />
        </F>
      </Row>
      <Row>
        <F label="From Date" opt>
          <Inp type="date" value={d.fromDate} onChange={v => set("fromDate", v)} />
        </F>
        <F label="To Date" opt>
          <Inp type="date" value={d.toDate} onChange={v => set("toDate", v)} />
        </F>
      </Row>
      <Row half>
        <F label="Reason for Leaving" opt>
          <Inp value={d.reasonLeaving} onChange={v => set("reasonLeaving", v)} placeholder="e.g. Career growth" />
        </F>
      </Row>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 5 — Document Upload
══════════════════════════════════════════════════════════════ */
const DOC_LIST: { key: DocKey; label: string; required: boolean }[] = [
  { key: "aadhaar",    label: "Aadhaar Card",                required: true  },
  { key: "pan",        label: "PAN Card",                    required: true  },
  { key: "degree",     label: "Degree Certificate",          required: true  },
  { key: "experience", label: "Experience / Relieving Letter", required: false },
  { key: "offer",      label: "Signed Offer Letter",         required: true  },
  { key: "photo",      label: "Passport-size Photograph",    required: true  },
];

function StepDocuments({ d, toggle }: {
  d: FormData["docs"];
  toggle: (k: DocKey) => void;
}) {
  const uploadedCount = Object.values(d).filter(Boolean).length;
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2.5 px-4 py-3 rounded-lg mb-2"
        style={{ background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.18)" }}>
        <i className="ti ti-info-circle text-[15px] mt-0.5 flex-shrink-0" style={{ color: "var(--primary)" }} />
        <p className="text-[13px]" style={{ color: "var(--primary)" }}>
          Upload clear scans of all original documents. Accepted formats: PDF, JPG, PNG (max 5MB each).
        </p>
      </div>
      {DOC_LIST.map(doc => (
        <div key={doc.key}
          className="flex items-center justify-between px-4 py-3.5 rounded-lg border border-[var(--outline-v)] bg-white hover:border-[var(--primary)] transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: d[doc.key] ? "rgba(22,163,74,0.10)" : "rgba(30,78,140,0.08)" }}>
              <i className={`ti ${d[doc.key] ? "ti-file-check" : "ti-file-text"} text-[16px]`}
                style={{ color: d[doc.key] ? "var(--success)" : "var(--primary)" }} />
            </div>
            <div>
              <p className="text-[13px] font-medium text-[var(--on-bg)]">
                {doc.label}
                {!doc.required && <span className="ml-2 text-[11px] font-normal text-[var(--on-variant)]">(Optional)</span>}
                {doc.required && <span className="ml-0.5 text-[13px] font-bold" style={{ color: "var(--error)" }}>*</span>}
              </p>
              <p className="text-[11.5px] text-[var(--on-variant)] mt-0.5">
                {d[doc.key] ? "Uploaded successfully" : "Not yet uploaded"}
              </p>
            </div>
          </div>
          <button
            onClick={() => toggle(doc.key)}
            suppressHydrationWarning
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-[12.5px] font-medium border transition-colors ${
              d[doc.key]
                ? "border-[var(--success)] text-[var(--success)] bg-white"
                : "border-[var(--primary)] text-[var(--primary)] bg-white hover:bg-[rgba(30,78,140,0.06)]"
            }`}
          >
            <i className={`ti ${d[doc.key] ? "ti-check" : "ti-upload"} text-[14px]`} />
            {d[doc.key] ? "Uploaded" : "Upload"}
          </button>
        </div>
      ))}
      <p className="text-[12px] text-[var(--on-variant)] text-right">
        {uploadedCount} of {DOC_LIST.length} documents uploaded
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 6 — Bank Details
══════════════════════════════════════════════════════════════ */
function StepBank({ d, set, errs }: {
  d: FormData["bank"];
  set: (k: keyof FormData["bank"], v: string) => void;
  errs: Partial<Record<keyof FormData["bank"], string>>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2.5 px-4 py-3 rounded-lg mb-1"
        style={{ background: "rgba(217,119,6,0.07)", border: "1px solid rgba(217,119,6,0.25)" }}>
        <i className="ti ti-alert-triangle text-[15px] mt-0.5 flex-shrink-0" style={{ color: "#b45309" }} />
        <p className="text-[13px]" style={{ color: "#92400e" }}>
          Please ensure your bank details are accurate. Incorrect details may delay salary credit. Provide an account in your own name.
        </p>
      </div>
      <Row>
        <F label="Bank Name" err={errs.bankName}>
          <Sel value={d.bankName} onChange={v => set("bankName", v)}>
            {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
          </Sel>
        </F>
        <F label="Account Holder Name" err={errs.accountHolder}>
          <Inp value={d.accountHolder} onChange={v => set("accountHolder", v)} placeholder="As per bank records" err={!!errs.accountHolder} />
        </F>
      </Row>
      <Row>
        <F label="Account Number" err={errs.accountNumber}>
          <Inp value={d.accountNumber} onChange={v => set("accountNumber", v)} placeholder="e.g. 123456789012" err={!!errs.accountNumber} />
        </F>
        <F label="Confirm Account Number" err={errs.confirmAccount}>
          <Inp value={d.confirmAccount} onChange={v => set("confirmAccount", v)} placeholder="Re-enter account number" err={!!errs.confirmAccount} />
        </F>
      </Row>
      <Row>
        <F label="IFSC Code" err={errs.ifsc}>
          <Inp value={d.ifsc} onChange={v => set("ifsc", v.toUpperCase())} placeholder="e.g. HDFC0001234" err={!!errs.ifsc} />
        </F>
        <F label="Account Type">
          <Sel value={d.accountType} onChange={v => set("accountType", v)}>
            {ACCOUNT_TYPES.map(a => <option key={a} value={a}>{a}</option>)}
          </Sel>
        </F>
      </Row>
      <Row>
        <F label="Branch Name" opt>
          <Inp value={d.branchName} onChange={v => set("branchName", v)} placeholder="e.g. Indiranagar" />
        </F>
        <F label="UAN (if existing)" opt>
          <Inp value={d.uan} onChange={v => set("uan", v)} placeholder="Optional" />
        </F>
      </Row>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   STEP 7 — Review & Submit
══════════════════════════════════════════════════════════════ */
function ReviewCard({ title, icon, onEdit, rows }: {
  title: string; icon: string; onEdit: () => void;
  rows: { label: string; value: string }[];
}) {
  return (
    <div className="rounded-xl border border-[var(--outline-v)] overflow-hidden mb-4">
      <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-low)] border-b border-[var(--outline-v)]">
        <div className="flex items-center gap-2">
          <i className={`ti ${icon} text-[14px]`} style={{ color: "var(--primary)" }} />
          <span className="text-[13px] font-semibold text-[var(--on-bg)]">{title}</span>
        </div>
        <button onClick={onEdit} suppressHydrationWarning
          className="flex items-center gap-1 text-[12px] font-medium px-3 py-1 rounded-lg border border-[var(--outline-v)] text-[var(--on-variant)] hover:text-[var(--primary)] hover:border-[var(--primary)] bg-white transition-colors">
          <i className="ti ti-pencil text-[13px]" /> Edit
        </button>
      </div>
      <div className="px-4 py-3 grid grid-cols-2 gap-x-8 gap-y-2.5">
        {rows.map(r => (
          <div key={r.label} className="flex flex-col">
            <span className="text-[11px] text-[var(--on-variant)] font-medium">{r.label}</span>
            <span className="text-[13px] text-[var(--on-bg)] font-medium mt-0.5">{r.value || "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StepReview({ form, goTo, declaration, setDeclaration }: {
  form: FormData; goTo: (step: number) => void;
  declaration: boolean; setDeclaration: (v: boolean) => void;
}) {
  const p = form.personal, e = form.employment, a = form.address, ed = form.education, b = form.bank;
  const uploadedCount = Object.values(form.docs).filter(Boolean).length;

  return (
    <div>
      <div className="flex items-start gap-2.5 px-4 py-3 rounded-lg mb-5"
        style={{ background: "rgba(22,163,74,0.07)", border: "1px solid rgba(22,163,74,0.25)" }}>
        <i className="ti ti-circle-check text-[15px] mt-0.5 flex-shrink-0" style={{ color: "var(--success)" }} />
        <p className="text-[13px] font-medium" style={{ color: "#15803d" }}>
          Almost done! Please review all the details below. You won&apos;t be able to edit after submission until HR reviews and either approves or requests changes.
        </p>
      </div>

      <ReviewCard title="Personal Information" icon="ti-user" onEdit={() => goTo(1)} rows={[
        { label: "Full Name",         value: `${p.firstName} ${p.lastName}`.trim() },
        { label: "Date of Birth",     value: p.dob },
        { label: "Gender",            value: p.gender },
        { label: "Phone",             value: p.phone },
        { label: "PAN",               value: p.pan },
        { label: "Aadhaar",           value: p.aadhaar },
        { label: "Emergency Contact", value: `${p.ecName}   ${p.ecPhone}`.trim() },
        { label: "Marital Status",    value: p.marital },
      ]} />

      <ReviewCard title="Employment Details" icon="ti-id" onEdit={() => goTo(2)} rows={[
        { label: "Department",         value: e.department },
        { label: "Designation",        value: e.designation },
        { label: "Branch / Location",  value: e.branch },
        { label: "Employee Type",      value: e.employeeType },
        { label: "Date of Joining",    value: e.dateOfJoining },
        { label: "Shift",              value: e.shift },
        { label: "Work Type",          value: e.workType },
        { label: "Weekly Days",        value: e.weeklyDays },
      ]} />

      <ReviewCard title="Address" icon="ti-map-pin" onEdit={() => goTo(3)} rows={[
        { label: "Street",   value: a.street },
        { label: "City",     value: a.city },
        { label: "PIN Code", value: a.pin },
        { label: "State",    value: a.state },
      ]} />

      <ReviewCard title="Education & Experience" icon="ti-school" onEdit={() => goTo(4)} rows={[
        { label: "Highest Qualification", value: `${ed.degree}${ed.specialisation ? ", " + ed.specialisation : ""}` },
        { label: "University",            value: ed.university },
        { label: "Year of Passing",       value: ed.yearOfPassing },
        { label: "Previous Employer",     value: ed.prevEmployer },
        { label: "Designation",           value: ed.prevDesignation },
      ]} />

      <ReviewCard title="Documents" icon="ti-file-description" onEdit={() => goTo(5)} rows={[
        { label: "Uploaded", value: `${uploadedCount} of ${DOC_LIST.length} documents` },
        { label: "Status",   value: uploadedCount >= 5 ? "All required docs uploaded" : "Some pending" },
      ]} />

      <ReviewCard title="Bank Details" icon="ti-building-bank" onEdit={() => goTo(6)} rows={[
        { label: "Bank",           value: b.bankName },
        { label: "Account Holder", value: b.accountHolder },
        { label: "Account Number", value: b.accountNumber ? "••••••" + b.accountNumber.slice(-4) : "" },
        { label: "IFSC",           value: b.ifsc },
      ]} />

      <label className="flex items-start gap-3 p-4 rounded-xl border border-[var(--outline-v)] bg-[var(--bg-low)] cursor-pointer mt-5">
        <input type="checkbox" checked={declaration} onChange={e => setDeclaration(e.target.checked)}
          suppressHydrationWarning className="w-4 h-4 mt-0.5 flex-shrink-0 cursor-pointer" style={{ accentColor: "var(--primary)" }} />
        <span className="text-[13px] text-[var(--on-bg)] leading-relaxed">
          I confirm that all the details provided above are accurate to the best of my knowledge. I understand that providing false information may lead to termination of employment.
        </span>
      </label>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   VALIDATION
══════════════════════════════════════════════════════════════ */
type StepErrors = Record<string, string | undefined>;

function validateStep(step: number, form: FormData): Record<string, string> {
  const e: Record<string, string> = {};
  if (step === 1) {
    const p = form.personal;
    if (!p.firstName.trim()) e.firstName = "Required";
    if (!p.lastName.trim())  e.lastName  = "Required";
    if (!p.email.trim())     e.email     = "Required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(p.email)) e.email = "Enter a valid email address";
    if (!p.dob)              e.dob       = "Required";
    if (!p.phone.trim())     e.phone     = "Required";
    if (!p.pan.trim())       e.pan       = "Required";
    if (!p.aadhaar.trim())   e.aadhaar   = "Required";
    if (!p.ecName.trim())    e.ecName    = "Required";
    if (!p.ecPhone.trim())   e.ecPhone   = "Required";
  }
  if (step === 2) {
    const emp = form.employment;
    if (!emp.designation.trim())   e.designation   = "Required";
    if (!emp.dateOfJoining)        e.dateOfJoining = "Required";
  }
  if (step === 3) {
    const a = form.address;
    if (!a.street.trim()) e.street = "Required";
    if (!a.city.trim())   e.city   = "Required";
    if (!a.pin.trim())    e.pin    = "Required";
  }
  if (step === 6) {
    const bk = form.bank;
    if (!bk.accountHolder.trim())    e.accountHolder  = "Required";
    if (!bk.accountNumber.trim())    e.accountNumber  = "Required";
    if (!bk.ifsc.trim())             e.ifsc           = "Required";
    if (bk.accountNumber && bk.confirmAccount && bk.accountNumber !== bk.confirmAccount)
      e.confirmAccount = "Account numbers do not match";
  }
  return e;
}

/* ══════════════════════════════════════════════════════════════
   MAIN WIZARD PAGE
══════════════════════════════════════════════════════════════ */
export default function NewEmployeePage() {
  const router = useRouter();
  const user = useCurrentUser();
  const [step,   setStep]   = useState(1);
  const [form,   setForm]   = useState<FormData>(EMPTY);
  const [errs,   setErrs]   = useState<StepErrors>({});
  const [submitted,   setSubmitted]   = useState(false);
  const [submitting,  setSubmitting]  = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [generatedId, setGeneratedId] = useState("");

  const p = form.personal;
  const displayName = [p.firstName, p.lastName].filter(Boolean).join(" ") || "New Employee";
  const displayRole = [form.employment.designation, form.employment.department].filter(Boolean).join(" • ") || "—";
  const initials    = [p.firstName[0], p.lastName[0]].filter(Boolean).join("").toUpperCase() || "NE";
  const pct         = Math.round(((step - 1) / TOTAL) * 100);

  // ── Field setters ────────────────────────────────────────
  function setPersonal(k: keyof FormData["personal"], v: string) {
    setForm(f => ({ ...f, personal: { ...f.personal, [k]: v } }));
    setErrs(e => ({ ...e, [k]: undefined }));
  }
  function setEmployment(k: keyof FormData["employment"], v: string) {
    setForm(f => ({ ...f, employment: { ...f.employment, [k]: v } }));
    setErrs(e => ({ ...e, [k]: undefined }));
  }
  function setAddress(k: keyof FormData["address"], v: string | boolean) {
    setForm(f => ({ ...f, address: { ...f.address, [k]: v } }));
    setErrs(e => ({ ...e, [k]: undefined }));
  }
  function setEducation(k: keyof FormData["education"], v: string) {
    setForm(f => ({ ...f, education: { ...f.education, [k]: v } }));
  }
  function toggleDoc(k: DocKey) {
    setForm(f => ({ ...f, docs: { ...f.docs, [k]: !f.docs[k] } }));
  }
  function setBank(k: keyof FormData["bank"], v: string) {
    setForm(f => ({ ...f, bank: { ...f.bank, [k]: v } }));
    setErrs(e => ({ ...e, [k]: undefined }));
  }

  // ── Navigation ───────────────────────────────────────────
  function next() {
    const errors = validateStep(step, form);
    if (Object.keys(errors).length > 0) { setErrs(errors); return; }
    setErrs({});
    if (step < TOTAL) setStep(s => s + 1);
  }
  function prev() {
    setErrs({});
    if (step > 1) setStep(s => s - 1);
  }
  function goTo(s: number) {
    setErrs({});
    setStep(s);
  }

  // ── Submit ───────────────────────────────────────────────
  async function submit() {
    if (!form.declaration) {
      setErrs({ declaration: "Please accept the declaration to proceed." });
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      const response = await clientApi.post(API.employees.list, {
        first_name:      form.personal.firstName.trim(),
        last_name:       form.personal.lastName.trim(),
        email:           form.personal.email.trim(),
        phone:           form.personal.phone.trim(),
        role:            "employee",
        department:      form.employment.department,
        designation:     form.employment.designation.trim(),
        branch:          form.employment.branch,
        date_of_joining: form.employment.dateOfJoining || null,
      });
      const data = response.data?.data ?? response.data;
      setGeneratedId((data as { employee_id?: string })?.employee_id ?? "");
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to create employee. Please try again.";
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  // ── Success screen ───────────────────────────────────────
  if (submitted) {
    return (
      <div className="max-w-xl mx-auto mt-16 text-center">
        <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
          style={{ background: "rgba(22,163,74,0.12)" }}>
          <i className="ti ti-circle-check text-[44px]" style={{ color: "var(--success)" }} />
        </div>
        <h2 className="text-[22px] font-bold text-[var(--on-bg)] mb-2">Employee Added Successfully!</h2>
        <p className="text-[14px] text-[var(--on-variant)] mb-5">
          {displayName} has been added and their login credentials have been sent by email.
        </p>
        {generatedId && (
          <div className="inline-flex flex-col items-center gap-1 px-8 py-4 rounded-2xl mb-8 border"
            style={{ background: "rgba(30,78,140,0.06)", borderColor: "rgba(30,78,140,0.2)" }}>
            <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: "var(--primary)", opacity: 0.7 }}>
              Employee ID
            </span>
            <span className="text-[28px] font-black tracking-widest" style={{ color: "var(--primary)", fontFamily: "monospace" }}>
              {generatedId}
            </span>
            <span className="text-[11px]" style={{ color: "var(--on-variant)" }}>
              Format: RSS + Initial + Joining Date + Surname
            </span>
          </div>
        )}
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => router.push("/dashboard/employees")} suppressHydrationWarning
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-[14px] font-semibold text-white shadow-md"
            style={{ background: "var(--primary)" }}>
            <i className="ti ti-arrow-left text-[16px]" />
            Back to Employees
          </button>
          <button onClick={() => { setForm(EMPTY); setStep(1); setSubmitted(false); setGeneratedId(""); }} suppressHydrationWarning
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-[14px] font-semibold border"
            style={{ color: "var(--on-variant)", borderColor: "var(--outline-v)" }}>
            <i className="ti ti-plus text-[16px]" />
            Add Another
          </button>
        </div>
      </div>
    );
  }

  const currentStep = STEPS[step - 1];

  return (
    <div className="max-w-2xl mx-auto">

      {/* ── Welcome Card ──────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[var(--outline-v)] p-5 mb-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center text-[15px] font-bold text-white flex-shrink-0"
          style={{ background: "var(--primary)" }}>
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-[16px] font-bold text-[var(--on-bg)] leading-tight">Welcome, {displayName}</h1>
          <p className="text-[12.5px] text-[var(--on-variant)] mt-0.5 truncate">
            {displayRole} at {user?.companyName}
          </p>
        </div>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold flex-shrink-0"
          style={{ background: "rgba(22,163,74,0.10)", color: "var(--success)" }}>
          <i className="ti ti-check text-[12px]" /> Onboarding
        </span>
      </div>

      {/* ── Step Indicator ───────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[var(--outline-v)] px-4 py-4 mb-4">
        <div className="flex items-center justify-between gap-1 overflow-x-auto">
          {STEPS.map((s, idx) => {
            const done    = step > s.id;
            const active  = step === s.id;
            const pending = step < s.id;
            return (
              <div key={s.id} className="flex items-center flex-shrink-0">
                {/* connector */}
                {idx > 0 && (
                  <div className="w-6 h-0.5 mx-1 flex-shrink-0 rounded-full transition-colors"
                    style={{ background: done || active ? "var(--primary)" : "var(--outline-v)" }} />
                )}
                {/* circle + label */}
                <button onClick={() => done && goTo(s.id)} suppressHydrationWarning
                  className={`flex flex-col items-center gap-1 transition-opacity ${done ? "cursor-pointer" : "cursor-default"}`}
                  style={{ opacity: pending ? 0.5 : 1 }}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold border-2 transition-all flex-shrink-0 ${
                    done   ? "border-[var(--primary)] text-white"
                    : active ? "border-[var(--primary)] text-[var(--primary)] bg-white"
                    : "border-[var(--outline-v)] text-[var(--on-variant)] bg-white"
                  }`}
                    style={done ? { background: "var(--primary)" } : {}}>
                    {done ? <i className="ti ti-check text-[13px]" /> : s.id}
                  </div>
                  <div className="text-center" style={{ minWidth: 44 }}>
                    <p className="text-[9px] font-semibold uppercase tracking-wide text-[var(--on-variant)]">STEP {s.id}</p>
                    <p className={`text-[10px] font-medium ${active ? "text-[var(--primary)]" : "text-[var(--on-variant)]"}`}>{s.short}</p>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Form Card ─────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[var(--outline-v)] overflow-hidden">
        {/* Section header */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-[var(--outline-v)]">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: "rgba(30,78,140,0.10)" }}>
            <i className={`ti ${currentStep.icon} text-[20px]`} style={{ color: "var(--primary)" }} />
          </div>
          <div>
            <h2 className="text-[16px] font-bold text-[var(--on-bg)]">{currentStep.label}</h2>
            <p className="text-[12.5px] text-[var(--on-variant)] mt-0.5">{currentStep.sub}</p>
          </div>
        </div>

        {/* Form body */}
        <div className="px-6 py-6">
          {step === 1 && <StepPersonal   d={form.personal}   set={setPersonal}   errs={errs} />}
          {step === 2 && <StepEmployment d={form.employment} set={setEmployment} errs={errs} />}
          {step === 3 && <StepAddress    d={form.address}     setAddr={setAddress} errs={errs} />}
          {step === 4 && <StepEducation  d={form.education}   set={setEducation} />}
          {step === 5 && <StepDocuments  d={form.docs}        toggle={toggleDoc} />}
          {step === 6 && <StepBank       d={form.bank}        set={setBank}      errs={errs} />}
          {step === 7 && (
            <StepReview
              form={form}
              goTo={goTo}
              declaration={form.declaration}
              setDeclaration={v => setForm(f => ({ ...f, declaration: v }))}
            />
          )}
          {errs.declaration && (
            <p className="text-[12px] font-medium mt-3" style={{ color: "var(--error)" }}>
              <i className="ti ti-alert-circle mr-1" />{errs.declaration}
            </p>
          )}
        </div>

        {/* Footer nav */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--outline-v)] bg-[var(--bg-low)]">
          <button onClick={prev} disabled={step === 1} suppressHydrationWarning
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium border border-[var(--outline-v)] text-[var(--on-bg)] bg-white hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            <i className="ti ti-arrow-left text-[14px]" /> Previous
          </button>
          <div className="text-[12.5px] text-[var(--on-variant)] font-medium text-center">
            Step {step} of {TOTAL} · {pct}% complete
          </div>
          {step < TOTAL ? (
            <button onClick={next} suppressHydrationWarning
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white transition-colors shadow-sm"
              style={{ background: "var(--primary)" }}>
              Continue <i className="ti ti-arrow-right text-[14px]" />
            </button>
          ) : (
            <div className="flex flex-col items-end gap-2">
              {submitError && (
                <p className="text-[12px] font-medium" style={{ color: "var(--error)" }}>
                  <i className="ti ti-alert-circle mr-1" />{submitError}
                </p>
              )}
              <button onClick={submit} disabled={submitting} suppressHydrationWarning
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white transition-colors shadow-sm"
                style={{ background: submitting ? "#94a3b8" : "var(--success)", cursor: submitting ? "not-allowed" : "pointer" }}>
                {submitting
                  ? <><i className="ti ti-loader-2 animate-spin text-[14px]" /> Creating…</>
                  : <><i className="ti ti-send text-[14px]" /> Create Employee</>}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
