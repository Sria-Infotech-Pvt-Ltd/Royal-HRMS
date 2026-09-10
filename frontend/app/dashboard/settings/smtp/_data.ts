// ─── Endpoints ───────────────────────────────────────────────────────────────
export const SMTP_BASE    = "/settings/smtp/";
export const smtpDetail   = (id: number) => `/settings/smtp/${id}/`;
export const smtpActivate = (id: number) => `/settings/smtp/${id}/activate/`;
export const SMTP_TEST    = "/settings/smtp/test/";

// ─── API response types ───────────────────────────────────────────────────────

export type Priority          = "high" | "normal" | "low" | "";
export type ReceiverEmailType = "email_id" | "personal_email_id";

export interface ApiSmtpEntry {
  id:                   number;
  name:                 string;             // user-defined label, e.g. "Gmail SMTP"
  smtp_type:            string;
  smtp_type_display:    string;
  host:                 string;
  port:                 number;
  username:             string;
  password_display:     string;             // always "••••••••"
  use_tls:              boolean;
  sender_name:          string;
  from_email:           string;
  bcc_email:            string;
  priority:             Priority;
  receiver_email_type:  ReceiverEmailType;
  is_active:            boolean;
  updated_at:           string;
}

export interface ApiSmtpResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     ApiSmtpEntry[];
}

// ─── Form state ───────────────────────────────────────────────────────────────

export type SmtpType = "local" | "server";

export interface SmtpForm {
  smtpType:            SmtpType;
  name:                string;
  host:                string;   // local only
  port:                number;   // local only
  username:            string;   // local only
  password:            string;   // local only
  useTls:              boolean;  // local only
  senderName:          string;
  fromEmail:           string;
  bccEmail:            string;
  priority:            Priority;
  receiverEmailType:   ReceiverEmailType;
}

export type SmtpFormErrors = Partial<Record<keyof SmtpForm, string>>;

export const EMPTY_SMTP_FORM: SmtpForm = {
  smtpType:          "local",
  name:              "",
  host:              "",
  port:              587,
  username:          "",
  password:          "",
  useTls:            true,
  senderName:        "",
  fromEmail:         "",
  bccEmail:          "",
  priority:          "normal",
  receiverEmailType: "email_id",
};

// ─── Converters ───────────────────────────────────────────────────────────────

export function apiEntryToForm(entry: ApiSmtpEntry): SmtpForm {
  return {
    smtpType:          (entry.smtp_type as SmtpType) || "local",
    name:              entry.name,
    host:              entry.host,
    port:              entry.port,
    username:          entry.username,
    password:          "",
    useTls:            entry.use_tls,
    senderName:        entry.sender_name,
    fromEmail:         entry.from_email,
    bccEmail:          entry.bcc_email,
    priority:          entry.priority,
    receiverEmailType: entry.receiver_email_type,
  };
}

export function formToPayload(form: SmtpForm): Record<string, unknown> {
  const isLocal = form.smtpType === "local";
  return {
    smtp_type:           form.smtpType,
    name:                form.name,
    ...(isLocal ? {
      host:              form.host,
      port:              form.port,
      username:          form.username,
      ...(form.password ? { password: form.password } : {}),
      use_tls:           form.useTls,
    } : {}),
    sender_name:         form.senderName,
    from_email:          form.fromEmail,
    bcc_email:           form.bccEmail,
    priority:            form.priority,
    receiver_email_type: form.receiverEmailType,
  };
}

// ─── Validation ───────────────────────────────────────────────────────────────

export function validateSmtpForm(form: SmtpForm, isAdd: boolean): SmtpFormErrors {
  const e: SmtpFormErrors = {};
  if (!form.name.trim())      e.name      = "Configuration name is required";
  if (!form.fromEmail.trim()) e.fromEmail = "From email is required";
  if (form.smtpType === "local") {
    if (!form.host.trim())     e.host     = "Host is required";
    if (!form.username.trim()) e.username = "Username is required";
    if (isAdd && !form.password.trim()) e.password = "Password is required";
  }
  return e;
}

// ─── Mail provider picker ───────────────────────────────────────────────────
// A pure frontend prefill layer over the two real backend smtp_type values
// (local/server) — the provider itself is never sent to the backend. Cost
// blurbs are general public vendor-pricing knowledge, not verified live —
// double-check exact numbers before relying on them.

export type ProviderKey = "gmail" | "amazon_ses" | "zoho" | "brevo" | "resend" | "outlook365" | "custom" | "server";

export interface ProviderConfig {
  key:        ProviderKey;
  label:      string;
  icon:       string;
  color:      string;
  bg:         string;
  note:       string;                                    // one-line affordability blurb on the card
  smtpType:   SmtpType;                                   // "local" for every provider except "server"
  hostMatch?: RegExp;                                     // used only to infer provider when editing an existing entry
  prefill?:   { host: string; port: number; useTls: boolean };
  locked?:    boolean;                                    // true = host/port shown read-only (one fixed endpoint)
  helpText?:  string;                                     // short caption under Host
}

export const PROVIDER_CONFIG: Record<ProviderKey, ProviderConfig> = {
  gmail: {
    key: "gmail", label: "Gmail", icon: "ti-brand-gmail", color: "#ea4335", bg: "rgba(234,67,53,0.1)",
    note: "Free, but capped at ~500 emails/day — best for testing or very small teams.",
    smtpType: "local", hostMatch: /gmail\.com/i,
    prefill: { host: "smtp.gmail.com", port: 587, useTls: true }, locked: true,
    helpText: "Use a Google App Password, not your normal account password.",
  },
  amazon_ses: {
    key: "amazon_ses", label: "Amazon SES", icon: "ti-brand-aws", color: "#ff9900", bg: "rgba(255,153,0,0.1)",
    note: "Usage-based (~$0.10 per 1,000 emails) — cheapest option once you're sending real volume.",
    smtpType: "local", hostMatch: /amazonaws\.com/i,
    prefill: { host: "email-smtp.us-east-1.amazonaws.com", port: 587, useTls: true },
    helpText: "Host varies by AWS region — replace the region segment with the region your SES identity is verified in.",
  },
  zoho: {
    key: "zoho", label: "Zoho Mail", icon: "ti-mail-check", color: "#d6193d", bg: "rgba(214,25,61,0.1)",
    note: "Free for up to 5 users — a solid low-cost choice for small orgs.",
    smtpType: "local", hostMatch: /zoho\./i,
    prefill: { host: "smtp.zoho.com", port: 587, useTls: true },
    helpText: "Use smtp.zoho.in / smtp.zoho.eu instead if your Zoho account's data center is India or Europe.",
  },
  brevo: {
    key: "brevo", label: "Brevo (Sendinblue)", icon: "ti-send", color: "#0b996e", bg: "rgba(11,153,110,0.1)",
    note: "Generous free tier — a good no-cost starting point.",
    smtpType: "local", hostMatch: /brevo\.com|sendinblue\.com/i,
    prefill: { host: "smtp-relay.brevo.com", port: 587, useTls: true }, locked: true,
  },
  resend: {
    key: "resend", label: "Resend", icon: "ti-rocket", color: "#7c3aed", bg: "rgba(124,58,237,0.1)",
    note: "Developer-friendly, generous free tier (a few thousand emails/month) — strong deliverability, quick setup.",
    smtpType: "local", hostMatch: /resend\.com/i,
    prefill: { host: "smtp.resend.com", port: 587, useTls: true }, locked: true,
    helpText: "Username is literally \"resend\" — the password field is your Resend API key, not an account password.",
  },
  outlook365: {
    key: "outlook365", label: "Outlook / Office 365", icon: "ti-brand-office", color: "#0078d4", bg: "rgba(0,120,212,0.1)",
    note: "Often already included free with an existing Microsoft 365 subscription.",
    smtpType: "local", hostMatch: /office365\.com|outlook\.com/i,
    prefill: { host: "smtp.office365.com", port: 587, useTls: true }, locked: true,
  },
  custom: {
    key: "custom", label: "Custom SMTP", icon: "ti-adjustments-horizontal", color: "#64748b", bg: "rgba(100,116,139,0.1)",
    note: "Bring your own host — for SendGrid, Mailgun, a corporate relay, or anything not listed above.",
    smtpType: "local",
  },
  server: {
    key: "server", label: "Dedicated Mail Server", icon: "ti-server", color: "#475569", bg: "rgba(71,85,105,0.1)",
    note: "Use the server's own built-in mail system — no external credentials needed.",
    smtpType: "server",
  },
};

export const PROVIDER_LIST: ProviderConfig[] = [
  PROVIDER_CONFIG.gmail, PROVIDER_CONFIG.amazon_ses, PROVIDER_CONFIG.zoho, PROVIDER_CONFIG.brevo,
  PROVIDER_CONFIG.resend, PROVIDER_CONFIG.outlook365, PROVIDER_CONFIG.custom, PROVIDER_CONFIG.server,
];

export function inferProviderKey(entry: ApiSmtpEntry): ProviderKey {
  if (entry.smtp_type !== "local") return "server";
  const host = (entry.host || "").toLowerCase();
  const match = PROVIDER_LIST.find(p => p.hostMatch?.test(host));
  return match?.key ?? "custom";
}

export function applyProvider(form: SmtpForm, key: ProviderKey): SmtpForm {
  const p = PROVIDER_CONFIG[key];
  return {
    ...form,
    smtpType: p.smtpType,
    ...(p.prefill ? { host: p.prefill.host, port: p.prefill.port, useTls: p.prefill.useTls } : {}),
  };
}
