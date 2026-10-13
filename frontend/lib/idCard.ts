// Employee ID card — shared types and pure helpers for the front/back
// template (components/idcard/IdCardFaces.tsx), the Settings → ID Card page
// and the per-employee print page.
//
// Card size matches the approved reference PDF's page (141.75 × 240.75 pt
// = 50 × 85 mm, portrait).

export const CARD_WIDTH_MM  = 50;
export const CARD_HEIGHT_MM = 85;

export type PrintLayout = "card" | "a4";

export interface IdCardEmployee {
  employee_id:         string | null;
  full_name:           string | null;
  designation:         string | null;
  department:          string | null;
  date_of_joining:     string | null;
  date_of_birth:       string | null;
  blood_group:         string | null;
  location:            string | null;
  photo_url:           string | null;
  residential_address: string | null;
  phone:               string | null;
  email:               string | null;
}

export interface IdCardCompany {
  name:           string | null;
  logo_url:       string | null;
  website:        string | null;
  website_url:    string | null;
  office_address: string | null;
}

export interface IdCardConfig {
  terms:                    string[];
  signature_url:            string | null;
  signatory_label:          string;
  show_date_of_birth:       boolean;
  show_residential_address: boolean;
  show_contact_details:     boolean;
}

export interface IdCardData {
  employee: IdCardEmployee;
  company:  IdCardCompany;
  card:     IdCardConfig;
  missing:  string[];
}

export interface FrontRow {
  key:   string;
  icon:  string;
  label: string;
  value: string;
}

/** Front-side detail rows in the reference order. Rows with no value on
 *  record are left off the card entirely — never printed blank or guessed. */
export function frontRows(emp: IdCardEmployee): FrontRow[] {
  const rows: (Omit<FrontRow, "value"> & { value: string | null })[] = [
    { key: "code",  icon: "ti-id-badge-2",    label: "Emp Code",    value: emp.employee_id },
    { key: "dob",   icon: "ti-cake",          label: "DOB",         value: emp.date_of_birth },
    { key: "doj",   icon: "ti-calendar",      label: "DOJ",         value: emp.date_of_joining },
    { key: "dept",  icon: "ti-building-bank", label: "Department",  value: emp.department },
    { key: "blood", icon: "ti-droplet-plus",  label: "Blood Group", value: emp.blood_group },
    { key: "loc",   icon: "ti-map-pin",       label: "Location",    value: emp.location },
  ];
  return rows.filter((r): r is FrontRow => !!r.value && !!r.value.trim());
}

/** Placeholder content for the Settings page's sample layout preview —
 *  bracketed labels, clearly not a real person. */
export function sampleCardData(company: IdCardCompany, card: IdCardConfig): IdCardData {
  return {
    employee: {
      employee_id: "[Emp Code]", full_name: "[Employee Name]", designation: "[Designation]",
      department: "[Department]", date_of_joining: "DD/MM/YYYY",
      date_of_birth: card.show_date_of_birth ? "DD/MM/YYYY" : null,
      blood_group: "[Blood Group]", location: "[Location]", photo_url: null,
      residential_address: card.show_residential_address ? "[Residential address]" : null,
      phone: card.show_contact_details ? "[Phone]" : null,
      email: card.show_contact_details ? "[Email]" : null,
    },
    company,
    card,
    missing: [],
  };
}

export function termsFromText(text: string, defaults: string, companyName: string | null): string[] {
  const source = text.trim() ? text : defaults;
  return source
    .split("\n")
    .map(l => l.trim())
    .filter(Boolean)
    .map(l => l.replaceAll("{company}", companyName || "the company"));
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Print stylesheet for the print sheet portal (IdCardPrintSheet), which is
 * mounted directly under <body>. Everything else in <body> — sidebar, header,
 * buttons, chat widget — is hidden for print. Card size is fixed in mm so
 * the browser never stretches it; "fit to page" scaling must stay off.
 *
 *  - "card": one face per page at exact card size (card printers / cut stock).
 *  - "a4":   both faces side by side at actual size on one A4 sheet with
 *            dashed cut guides (regular office printers).
 */
export function idCardPrintCss(layout: PrintLayout): string {
  const page = layout === "card"
    ? `@page { size: ${CARD_WIDTH_MM}mm ${CARD_HEIGHT_MM}mm; margin: 0; }`
    : `@page { size: A4 portrait; margin: 15mm; }`;
  const sheet = layout === "card"
    ? `.idc-print-root { display: block !important; }
       .idc-print-face { break-after: page; page-break-after: always; }
       .idc-print-face:last-child { break-after: auto; page-break-after: auto; }`
    : `.idc-print-root { display: flex !important; gap: 10mm; justify-content: center; align-items: flex-start; }
       .idc-print-face { outline: 0.2mm dashed #9aa3b8; outline-offset: 1mm; }`;
  return `
.idc-print-root { display: none; }
@media print {
  ${page}
  html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
  body > *:not(.idc-print-root) { display: none !important; }
  ${sheet}
  .idc-print-face { width: ${CARD_WIDTH_MM}mm; height: ${CARD_HEIGHT_MM}mm; overflow: hidden; zoom: 1; }
  .idc-print-root * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}`;
}
