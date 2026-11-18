// Look of the Timesheets / Personnel actions / Face registration tabs. Scoped under .tb-* so nothing else is touched.
const APPROVAL_TAB_CSS = `
.tb-head{position:relative;overflow:hidden;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 16px;padding:16px 20px;border-bottom:1px solid var(--outline-v);background:linear-gradient(135deg,color-mix(in srgb,var(--tb-accent) 9%,transparent),transparent 60%)}
.tb-head::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--tb-accent)}
.tb-head-main{display:flex;align-items:center;gap:12px;min-width:0}
.tb-head h2{margin:0;font-size:16px;font-weight:800;color:var(--on-bg)}
.tb-head p{margin:2px 0 0;font-size:12px;color:var(--on-variant)}
.tb-icon{flex:none;display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:13px;font-size:21px;color:#fff;background:var(--tb-accent);box-shadow:0 6px 14px color-mix(in srgb,var(--tb-accent) 35%,transparent)}
.tb-actions{display:flex;flex-wrap:wrap;gap:6px}
.tb-stats{flex-basis:100%;display:flex;flex-wrap:wrap;gap:8px}
.tb-stat{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:99px;font-size:12px;font-weight:700;color:var(--tb-stat);background:color-mix(in srgb,var(--tb-stat) 11%,transparent)}
.tb-stat b{font-size:13px;color:var(--on-bg)}
.tb-stat.is-urgent{background:var(--tb-stat);color:#fff}
.tb-stat.is-urgent b{color:#fff}
.tb-avatar{flex:none;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;font-size:11.5px;font-weight:800;color:var(--primary);background:color-mix(in srgb,var(--primary) 13%,transparent)}
.tb-person{display:flex;align-items:center;gap:10px}
.tb-sub{font-size:11px;color:var(--on-variant)}
.tb-hours{min-width:96px}
.tb-hours b{font-size:13px;color:var(--on-bg)}
.tb-meter{height:5px;margin-top:5px;border-radius:99px;background:color-mix(in srgb,var(--on-variant) 14%,transparent);overflow:hidden}
.tb-meter i{display:block;height:100%;border-radius:99px;background:var(--tb-meter,#16a34a)}
.tb-table tbody tr{transition:background .12s ease}
.tb-table tbody tr:hover{background:color-mix(in srgb,var(--primary) 4%,transparent)}
.tb-empty{display:flex;flex-direction:column;align-items:center;padding:44px 20px;text-align:center}
.tb-empty-icon{display:inline-flex;align-items:center;justify-content:center;width:62px;height:62px;border-radius:50%;font-size:28px;color:#16a34a;background:color-mix(in srgb,#16a34a 13%,transparent)}
.tb-empty-title{margin-top:12px;font-size:15px;font-weight:800;color:var(--on-bg)}
.tb-empty-hint{margin-top:4px;max-width:420px;font-size:12.5px;color:var(--on-variant)}
.tb-switch{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.tb-switch.is-on{border-color:var(--primary);color:var(--primary);background:color-mix(in srgb,var(--primary) 8%,transparent)}
.tb-switch input{accent-color:var(--primary)}
.tb-score{display:flex;align-items:center;gap:8px;min-width:110px}
.tb-score .tb-meter{flex:1;margin:0}
.tb-score span{font-family:Menlo,Consolas,monospace;font-size:12px;font-weight:700}
.tb-body{padding:6px 16px 16px}
.tb-cases{display:flex;flex-direction:column;gap:10px;padding:14px 16px 16px}
.tb-case{padding:4px 14px;border:1px solid var(--outline-v);border-radius:14px;background:var(--surface,#fff);overflow-x:auto;transition:box-shadow .15s ease,border-color .15s ease}
.tb-case:hover{border-color:color-mix(in srgb,var(--primary) 40%,var(--outline-v));box-shadow:0 8px 20px rgba(76,29,149,.08)}
.tb-case .case-row{border-top:none;min-width:720px}
`;

export function ApprovalTabStyles() {
  return <style>{APPROVAL_TAB_CSS}</style>;
}
