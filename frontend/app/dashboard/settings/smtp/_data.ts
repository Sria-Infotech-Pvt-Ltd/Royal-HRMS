// ─── Endpoints ───────────────────────────────────────────────────────────────
export const SMTP_BASE    = "/settings/smtp/";
export const smtpDetail   = (id: number) => `/settings/smtp/${id}/`;
export const smtpActivate = (id: number) => `/settings/smtp/${id}/activate/`;
export const SMTP_TEST    = "/settings/smtp/test/";

// ─── API response types ───────────────────────────────────────────────────────

export type Priority          = "high" | "normal" | "low" | "";
export type ReceiverEmailType = "email_id" | "personal_email_id";

// Purely a UI label layered on the existing generic host/port/username/
// password/use_tls fields — every provider below sends over plain SMTP,
// so the backend's actual send path never reads this. "" (blank) is what
// every pre-existing row already has and is not something a config picks
// itself — it means "unspecified / pre-dates the provider picker".
export type Provider =
  | "" | "gmail" | "amazon_ses" | "zoho_mail" | "brevo"
  | "resend" | "outlook365" | "custom_smtp" | "dedicated_server";

export interface ApiSmtpEntry {
  id:                   number;
  name:                 string;             // user-defined label, e.g. "Gmail SMTP"
  smtp_type:            string;
  smtp_type_display:    string;
  provider:             Provider;
  provider_display:     string;
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
  provider:            Provider;
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
  provider:          "",
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
    provider:          entry.provider || "",
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
    provider:            form.provider,
    name:                form.name,
    ...(isLocal ? {
      host:              form.host,
      port:              form.port,
      username:          form.username,
      ...(form.password ? { password: form.password } : {}),
      use_tls:           form.useTls,
    } : {
      // "Dedicated Mail Server" (smtp_type=server) hides host/username in
      // the form — the backend still requires both to be non-blank (they
      // have no `blank=True`), so fall back to safe, obviously-local
      // placeholders rather than sending them empty and failing validation.
      // Editing an already-saved server-type row is unaffected: its real
      // host/username came back from the API into form.host/form.username
      // via apiEntryToForm and simply pass through unchanged here.
      host:              form.host || "localhost",
      port:              form.port,
      username:          form.username || form.fromEmail || "server",
      use_tls:           form.useTls,
    }),
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

// ─── Provider picker (Add SMTP → choose provider → prefilled form) ────────────
//
// Purely a frontend convenience layer: picking a provider just prefills the
// existing generic host/port/TLS fields (and, for the three "fixed" ones,
// locks them) before handing off to the same form/payload/validation above.
// Nothing here is provider-specific on the backend — every provider sends
// over plain SMTP.

export const PROVIDER_ORDER: Exclude<Provider, "">[] = [
  "gmail", "amazon_ses", "zoho_mail",
  "brevo", "resend", "outlook365",
  "custom_smtp", "dedicated_server",
];

export interface ProviderMeta {
  value:       Exclude<Provider, "">;
  label:       string;
  description: string;
  icon:        string;   // Tabler icon class
  iconColor:   string;
  iconBg:      string;
}

export const PROVIDER_META: Record<Exclude<Provider, "">, ProviderMeta> = {
  gmail: {
    value: "gmail", label: "Gmail",
    description: "Free, but capped at ~500 emails/day — best for testing or very small teams.",
    icon: "ti-brand-gmail", iconColor: "#d93025", iconBg: "rgba(217,48,37,0.1)",
  },
  amazon_ses: {
    value: "amazon_ses", label: "Amazon SES",
    description: "Usage-based (~$0.10 per 1,000 emails) — cheapest option once you're sending real volume.",
    icon: "ti-brand-aws", iconColor: "#e07b00", iconBg: "rgba(255,153,0,0.12)",
  },
  zoho_mail: {
    value: "zoho_mail", label: "Zoho Mail",
    description: "Free for up to 5 users — a solid low-cost choice for small orgs.",
    icon: "ti-mail", iconColor: "#e42527", iconBg: "rgba(228,37,39,0.1)",
  },
  brevo: {
    value: "brevo", label: "Brevo (Sendinblue)",
    description: "Generous free tier — a good no-cost starting point.",
    icon: "ti-send", iconColor: "#0b8457", iconBg: "rgba(11,132,87,0.1)",
  },
  resend: {
    value: "resend", label: "Resend",
    description: "Developer-friendly, generous free tier (a few thousand emails/month) — strong deliverability, quick setup.",
    icon: "ti-rocket", iconColor: "#6c47ff", iconBg: "rgba(108,71,255,0.12)",
  },
  outlook365: {
    value: "outlook365", label: "Outlook / Office 365",
    description: "Often already included free with an existing Microsoft 365 subscription.",
    icon: "ti-mail-forward", iconColor: "#0078d4", iconBg: "rgba(0,120,212,0.12)",
  },
  custom_smtp: {
    value: "custom_smtp", label: "Custom SMTP",
    description: "Bring your own host — for SendGrid, Mailgun, a corporate relay, or anything not listed above.",
    icon: "ti-adjustments", iconColor: "var(--on-variant)", iconBg: "var(--bg-low)",
  },
  dedicated_server: {
    value: "dedicated_server", label: "Dedicated Mail Server",
    description: "Use the server's own built-in mail system — no external credentials needed.",
    icon: "ti-server-2", iconColor: "var(--on-variant)", iconBg: "var(--bg-low)",
  },
};

export interface ProviderPreset {
  smtpType:      SmtpType;
  host:          string;
  port:          number;
  useTls:        boolean;
  /** Host/Port/TLS are shown but disabled — this provider has exactly one
   *  correct value for them, so there's nothing to edit. */
  hostLocked:    boolean;
  /** Informational note shown under the Host field — either explains the
   *  lock, or (for SES/Zoho) how to adapt the prefilled value. */
  hostHint?:     string;
  /** Extra note shown under Username — only Resend needs this today. */
  usernameHint?: string;
  /** Dedicated Mail Server only — the whole host/port/username/password
   *  section is hidden, matching the existing "server" smtp_type form. */
  hideCredentials?: boolean;
}

const GOOGLE_APP_PASSWORD_LINK =
  'a Google <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" ' +
  'style="color:var(--primary)">App Password</a>, not your regular password';

export const PROVIDER_PRESETS: Record<Exclude<Provider, "">, ProviderPreset> = {
  gmail: {
    smtpType: "local", host: "smtp.gmail.com", port: 587, useTls: true, hostLocked: true,
    hostHint: `Fixed for Gmail — not editable. Requires ${GOOGLE_APP_PASSWORD_LINK}.`,
  },
  amazon_ses: {
    smtpType: "local", host: "email-smtp.us-east-1.amazonaws.com", port: 587, useTls: true, hostLocked: false,
    hostHint: "Host varies by AWS region — replace the region segment with the region your SES identity is verified in.",
  },
  zoho_mail: {
    smtpType: "local", host: "smtp.zoho.com", port: 587, useTls: true, hostLocked: false,
    hostHint: "Use smtp.zoho.in / smtp.zoho.eu instead if your Zoho account's data center is India or Europe.",
  },
  brevo: {
    smtpType: "local", host: "smtp-relay.brevo.com", port: 587, useTls: true, hostLocked: true,
    hostHint: "Fixed for Brevo (Sendinblue) — not editable.",
  },
  resend: {
    smtpType: "local", host: "smtp.resend.com", port: 587, useTls: true, hostLocked: true,
    hostHint: "Fixed for Resend — not editable.",
    usernameHint: 'Username is literally "resend" — the password field is your Resend API key, not an account password.',
  },
  outlook365: {
    smtpType: "local", host: "smtp.office365.com", port: 587, useTls: true, hostLocked: true,
    hostHint: "Fixed for Outlook / Office 365 — not editable.",
  },
  custom_smtp: {
    smtpType: "local", host: "", port: 587, useTls: true, hostLocked: false,
  },
  dedicated_server: {
    smtpType: "server", host: "", port: 25, useTls: false, hostLocked: false,
    hideCredentials: true,
  },
};
