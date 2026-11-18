// Extra look for the Team Approvals tab (summary accents, quick date chips, waiting-time chips, richer empty state).
// Scoped under .tv-* so the existing .ta-* styles are untouched.
const TEAM_APPROVAL_CSS = `
.tv-card{position:relative;overflow:hidden}
.tv-card::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--tv-accent)}
.tv-hint{display:block;margin-top:3px;font-size:11px;font-weight:700;color:var(--tv-accent)}
.tv-hint.is-clear{color:#16a34a}
.tv-value{font-size:28px;line-height:1;font-weight:800}
.tv-chips{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:-4px 0 14px}
.tv-chips-label{font-size:11.5px;font-weight:700;color:var(--on-variant);margin-right:2px}
.tv-chip{padding:4px 11px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font:inherit;font-size:11.5px;font-weight:700;color:var(--on-variant);cursor:pointer}
.tv-chip:hover{border-color:var(--primary);color:var(--primary)}
.tv-chip.is-on{border-color:var(--primary);background:color-mix(in srgb,var(--primary) 10%,transparent);color:var(--primary)}
.tv-chip.is-clear{border-style:dashed;color:#dc2626}
.tv-chip.is-clear:hover{border-color:#dc2626;color:#dc2626}
.tv-wait{display:inline-flex;align-items:center;gap:4px;margin-top:4px;padding:2px 8px;border-radius:99px;font-size:10.5px;font-weight:800;color:var(--tv-wait);background:color-mix(in srgb,var(--tv-wait) 13%,transparent)}
.tv-wait.is-fresh{--tv-wait:#16a34a}
.tv-wait.is-aging{--tv-wait:#d97706}
.tv-wait.is-late{--tv-wait:#dc2626}
tr.tv-late-row>td:first-child{box-shadow:inset 3px 0 0 #dc2626}
tr.tv-aging-row>td:first-child{box-shadow:inset 3px 0 0 #d97706}
.tv-empty-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-top:16px}
.tv-empty-tips{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 18px;margin-top:18px;font-size:11.5px;color:var(--on-variant)}
.tv-empty-tips i{margin-right:5px;color:var(--primary)}
`;

export function TeamApprovalStyles() {
  return <style>{TEAM_APPROVAL_CSS}</style>;
}
