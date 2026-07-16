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
