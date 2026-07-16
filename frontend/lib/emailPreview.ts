export interface CompanyInfo {
  company_name: string;
  logo:         string;
  logo_url:     string;
  website:      string;
  official_phone: string;
  address:      string;
  city:         string;
  state:        string;
}

/**
 * Expands a vars map to include uppercase and lowercase variants of every key,
 * so the backend substitutes {FNAME}, {fname}, {Fname} all from the same source.
 */
export function normalizeExtraContext(
  vars: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(vars)) {
    out[key]               = value;
    out[key.toLowerCase()] = value;
    out[key.toUpperCase()] = value;
  }
  return out;
}

/**
 * Renders template variable placeholders with real values.
 * Leaves any unrecognised {variable} visible so the user can see what remains.
 */
export function renderTemplateVars(
  text: string,
  vars: Record<string, string>,
): string {
  // Build a lowercase-keyed lookup so matching is case-insensitive
  const lookup: Record<string, string> = {};
  for (const [key, value] of Object.entries(vars)) {
    lookup[key.toLowerCase()] = value;
  }
  // Replace every {ANYTHING} placeholder, case-insensitive
  return text.replace(/\{([^}]+)\}/g, (_match, tag: string) => {
    const normalized = tag.toLowerCase();
    return normalized in lookup
      ? (lookup[normalized] || `[${tag}]`)
      : `{${tag}}`;
  });
}

/**
 * Wraps a rendered email body with the company header (logo + name) and footer.
 * Mirrors the backend _company_email_wrapper helper in accounts/utils.py.
 */
export function buildEmailPreview(
  body: string,
  company: CompanyInfo | null,
): string {
  const name    = company?.company_name ?? '[Company]';
  const logoUrl = company?.logo_url ?? company?.logo ?? '';
  const website = company?.website ?? '';
  const addr    = [company?.address, company?.city, company?.state]
    .filter(Boolean)
    .join(', ');
  const footerParts = [website, addr].filter(Boolean);
  const footer  = footerParts.length ? footerParts.join(' &nbsp;|&nbsp; ') : name;

  const logoHtml = logoUrl
    ? `<img src="${logoUrl}" alt="${name}"
           style="max-height:70px;max-width:220px;object-fit:contain;" />`
    : `<span style="font-size:18px;font-weight:700;color:#1a1a2e;">${name}</span>`;

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body { margin:0; background:#f4f4f7;
         font-family:Arial,Helvetica,sans-serif; }
</style>
</head>
<body>
<div style="background:#f4f4f7;padding:24px 0;">
  <div style="max-width:600px;margin:0 auto;background:#fff;
              border-radius:8px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,0.08);">

    <div style="background:#fff;text-align:center;
                padding:24px 40px 18px;
                border-bottom:3px solid #4f46e5;">
      ${logoHtml}
    </div>

    <div style="padding:28px 36px;color:#333;line-height:1.7;font-size:15px;">
      ${body}
    </div>

    <div style="background:#f8f8fb;text-align:center;
                padding:14px 24px;font-size:12px;color:#888;
                border-top:1px solid #eee;">
      ${footer}
    </div>

  </div>
</div>
<!-- prevent Gmail from collapsing footer as trimmed content -->
<div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f4f4f7;">
  &zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
</div>
</body>
</html>`;
}
