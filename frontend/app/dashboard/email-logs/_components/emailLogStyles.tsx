// Look of the Email Logs screen (aligned filter bar, status chips, summary strip, expandable rows). Scoped under .el-*.
const EMAIL_LOG_CSS = `
.el-filters{margin-bottom:16px;padding:16px 18px}
.el-filter-row{display:grid;grid-template-columns:minmax(200px,1fr) 170px minmax(370px,auto) auto;gap:12px;align-items:end}
@media(max-width:1280px){.el-filter-row{grid-template-columns:repeat(2,minmax(0,1fr))}.el-f-grow{grid-column:1/-1}}
@media(max-width:560px){.el-filter-row{grid-template-columns:minmax(0,1fr)}}
.el-f{display:flex;flex-direction:column;gap:6px;min-width:0}
.el-f>span{font-size:12px;font-weight:700;color:var(--on-variant)}
.el-f .field-input,.el-search{height:42px;box-sizing:border-box}
.el-f .field-input{width:100%}
.el-search{display:flex;align-items:center;gap:8px;padding:0 12px;border:1.5px solid var(--outline-v);border-radius:var(--radius);background:var(--surface,#fff);box-shadow:0 1px 2px rgba(20,21,31,.04)}
.el-search:focus-within{border-color:var(--primary)}
.el-search i{color:var(--on-variant);font-size:16px}
.el-search input{flex:1;min-width:0;border:none;outline:none;background:transparent;color:var(--on-bg);font:inherit;font-size:13px}
.el-dates{display:grid;grid-template-columns:minmax(160px,1fr) auto minmax(160px,1fr);gap:8px;align-items:end;min-width:0}
.el-dates>b{padding-bottom:12px;font-size:12px;font-weight:600;color:var(--on-variant)}
@media(max-width:1280px){.el-dates{grid-column:span 2}}
@media(max-width:560px){.el-dates{grid-column:auto}}
.el-chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid var(--outline-v)}
.el-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 13px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font:inherit;font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.el-chip:hover{border-color:var(--primary);color:var(--primary)}
.el-chip.is-on{border-color:var(--el-accent,var(--primary));background:color-mix(in srgb,var(--el-accent,var(--primary)) 10%,transparent);color:var(--el-accent,var(--primary))}
.el-strip{display:flex;flex-wrap:wrap;gap:8px;margin-left:auto}
.el-stat{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:99px;font-size:12px;font-weight:700;color:var(--el-stat);background:color-mix(in srgb,var(--el-stat) 11%,transparent)}
.el-stat b{color:var(--on-bg)}
.el-stat.is-urgent{background:var(--el-stat);color:#fff}
.el-stat.is-urgent b{color:#fff}
.el-person{display:flex;align-items:center;gap:10px;min-width:0}
.el-avatar{flex:none;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;font-size:15px;color:var(--el-tone);background:color-mix(in srgb,var(--el-tone) 14%,transparent)}
.el-tone-sent{--el-tone:#16a34a}
.el-tone-failed{--el-tone:#dc2626}
.el-to{font-size:12.5px;font-weight:600;color:var(--on-bg);overflow:hidden;text-overflow:ellipsis}
.el-subject{font-size:13px;color:var(--on-bg)}
.el-template{display:inline-block;padding:2px 8px;border-radius:6px;font-family:Menlo,Consolas,monospace;font-size:11px;color:var(--on-variant);background:color-mix(in srgb,var(--on-variant) 9%,transparent)}
.el-row{cursor:pointer;transition:background .12s ease}
.el-row:hover{background:color-mix(in srgb,var(--primary) 4%,transparent)}
.el-row.is-open{background:color-mix(in srgb,var(--primary) 6%,transparent)}
.el-row.is-failed>td:first-child{box-shadow:inset 3px 0 0 #dc2626}
.el-detail td{padding:0!important;background:color-mix(in srgb,var(--on-variant) 4%,transparent)}
.el-detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px 20px;padding:14px 20px}
.el-detail-grid dt{font-size:10.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--on-variant)}
.el-detail-grid dd{margin:3px 0 0;font-size:12.5px;color:var(--on-bg);word-break:break-word}
.el-error{margin:0 20px 14px;padding:10px 14px;border-radius:10px;font-size:12.5px;color:#991b1b;background:rgba(220,38,38,.08);border:1px solid rgba(220,38,38,.25)}
@media(max-width:900px){.el-hide-md{display:none}}
.el-empty{display:flex;flex-direction:column;align-items:center;padding:44px 16px;text-align:center;color:var(--on-variant);font-size:13px}
.el-empty i{font-size:34px;color:var(--primary);margin-bottom:8px}
`;

export function EmailLogStyles() {
  return <style>{EMAIL_LOG_CSS}</style>;
}
