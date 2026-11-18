// Look of the My Approvals overview (summary tiles and workflow cards). Scoped under .ap-* so nothing else is touched.
const APPROVAL_OVERVIEW_CSS = `
.ap-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px}
@media(max-width:700px){.ap-summary{grid-template-columns:minmax(0,1fr)}}
.ap-tile{position:relative;overflow:hidden;display:flex;align-items:center;gap:14px;padding:16px 18px;border:1px solid var(--outline-v);border-radius:16px;background:var(--surface,#fff)}
.ap-tile::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--ap-accent)}
.ap-tile .ap-icon{width:42px;height:42px;font-size:21px}
.ap-tile b{display:block;font-size:28px;line-height:1;font-weight:800;color:var(--on-bg)}
.ap-tile span.ap-tile-label{display:block;margin-top:5px;font-size:11.5px;font-weight:800;letter-spacing:.05em;color:var(--on-variant);text-transform:uppercase}
.ap-bar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.ap-bar h2{margin:0;font-size:15px;font-weight:800;color:var(--on-bg);display:flex;align-items:center;gap:8px}
.ap-switch{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.ap-switch.is-on{border-color:var(--primary);color:var(--primary);background:color-mix(in srgb,var(--primary) 8%,transparent)}
.ap-switch input{accent-color:var(--primary)}
.ap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.ap-card{display:flex;flex-direction:column;gap:12px;padding:16px;border:1px solid var(--outline-v);border-radius:16px;background:var(--surface,#fff);transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
.ap-card:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(76,29,149,.10);border-color:color-mix(in srgb,var(--ap-accent) 45%,var(--outline-v))}
.ap-card.needs-me{border-color:color-mix(in srgb,var(--ap-accent) 55%,var(--outline-v));box-shadow:0 0 0 3px color-mix(in srgb,var(--ap-accent) 12%,transparent)}
.ap-card-top{display:flex;align-items:center;gap:10px}
.ap-card-top h3{flex:1;margin:0;font-size:14px;font-weight:800;color:var(--on-bg);min-width:0}
.ap-icon{flex:none;display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:11px;font-size:18px;color:var(--ap-accent);background:color-mix(in srgb,var(--ap-accent) 14%,transparent)}
.ap-flag{flex:none;padding:3px 9px;border-radius:99px;font-size:10.5px;font-weight:800;letter-spacing:.03em;color:#fff;background:var(--ap-accent)}
.ap-counts{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.ap-counts>div{padding:10px 12px;border-radius:12px;background:color-mix(in srgb,var(--on-variant) 6%,transparent)}
.ap-counts>div.is-hot{background:color-mix(in srgb,var(--ap-accent) 13%,transparent)}
.ap-counts b{display:block;font-size:24px;line-height:1.1;font-weight:800;color:var(--on-bg)}
.ap-counts span{font-size:11px;font-weight:700;color:var(--on-variant)}
.ap-uncounted{display:flex;align-items:center;gap:8px;padding:14px 12px;border-radius:12px;background:color-mix(in srgb,var(--on-variant) 6%,transparent);font-size:12px;font-weight:600;color:var(--on-variant)}
.ap-scope{flex:1;margin:0;font-size:12px;line-height:1.45;color:var(--on-variant);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.ap-card .btn{align-self:stretch;justify-content:center}
.ap-empty{padding:40px 16px;text-align:center;border:1px dashed var(--outline-v);border-radius:16px;color:var(--on-variant);font-size:13px}
.ap-empty i{display:block;font-size:30px;margin-bottom:8px;color:#16a34a}
.ap-views{display:inline-flex;padding:3px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff)}
.ap-views button{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border:none;border-radius:8px;background:none;font:inherit;font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.ap-views button.is-on{background:var(--primary);color:var(--on-primary,#fff)}
.ap-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ap-group{margin-bottom:16px}
.ap-group-head{display:flex;align-items:center;gap:8px;margin:0 0 8px 2px;font-size:11.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--on-variant)}
.ap-group-head span{padding:1px 8px;border-radius:99px;background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary)}
.ap-lines{border:1px solid var(--outline-v);border-radius:16px;background:var(--surface,#fff);overflow:hidden}
.ap-line{display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--outline-v);border-left:3px solid transparent;transition:background .12s ease}
.ap-line:first-child{border-top:none}
.ap-line:hover{background:color-mix(in srgb,var(--ap-accent) 5%,transparent)}
.ap-line.needs-me{border-left-color:var(--ap-accent)}
.ap-line-main{flex:1;min-width:0}
.ap-line-title{font-size:13.5px;font-weight:700;color:var(--on-bg)}
.ap-line-scope{margin-top:2px;font-size:12px;color:var(--on-variant);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ap-pill{flex:none;display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:99px;font-size:11.5px;font-weight:700;color:var(--on-variant);background:color-mix(in srgb,var(--on-variant) 8%,transparent)}
.ap-pill.is-hot{color:var(--ap-accent);background:color-mix(in srgb,var(--ap-accent) 14%,transparent)}
@media(max-width:760px){.ap-line{flex-wrap:wrap}.ap-line-main{flex-basis:calc(100% - 60px)}.ap-line-scope{white-space:normal}}
.ap-note{margin:14px 2px 0;font-size:11px;color:var(--on-variant)}
`;

export function ApprovalOverviewStyles() {
  return <style>{APPROVAL_OVERVIEW_CSS}</style>;
}
