// Look of the report cards. Scoped under .rp-* so nothing else is touched.
const REPORT_CSS = `
.rp-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));max-width:1500px}
.rp-card{position:relative;overflow:hidden;transition:transform .15s ease,box-shadow .15s ease}
.rp-card::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--rp-accent)}
.rp-card:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(76,29,149,.10)}
.rp-card-head{display:flex;align-items:flex-start;gap:12px}
.rp-card-icon{flex:none;display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:12px;font-size:20px;color:var(--rp-accent);background:color-mix(in srgb,var(--rp-accent) 14%,transparent)}
.rp-filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.rp-filters label{min-width:0}
.rp-filters .field-input{width:100%}
.rp-filters label{font-weight:700;color:var(--on-variant)}
.rp-actions{display:flex;align-items:center;gap:8px;padding-top:12px;border-top:1px solid var(--outline-v)}
.rp-download{flex:1;justify-content:center;white-space:nowrap}
.rp-icon-btn{flex:none;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff);color:var(--on-variant);font-size:17px;cursor:pointer;transition:border-color .12s ease,color .12s ease}
.rp-icon-btn:hover,.rp-icon-btn.is-on{border-color:var(--rp-accent);color:var(--rp-accent)}
.rp-icon-btn.is-on{background:color-mix(in srgb,var(--rp-accent) 9%,transparent)}
@media(max-width:420px){.rp-filters{grid-template-columns:minmax(0,1fr)}}
`;

export function ReportStyles() {
  return <style>{REPORT_CSS}</style>;
}
