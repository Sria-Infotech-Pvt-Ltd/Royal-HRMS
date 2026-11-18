// Look of the Leave page cards (balance tiles, request / holiday / coverage rows). Scoped under .lv-* so nothing else is touched.
export const LEAVE_CSS = `
.lv-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
@media(max-width:1100px){.lv-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.lv-tiles{grid-template-columns:minmax(0,1fr)}}
.lv-tile{position:relative;overflow:hidden;background:var(--surface,#fff);border:1px solid var(--outline-v);border-radius:16px;padding:16px 18px;transition:transform .15s ease,box-shadow .15s ease}
.lv-tile:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(76,29,149,.10)}
.lv-tile::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--lv-accent,var(--primary))}
.lv-tile-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.lv-tile-label{font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--on-variant)}
.lv-icon{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;font-size:17px;color:var(--lv-accent,var(--primary));background:color-mix(in srgb,var(--lv-accent,var(--primary)) 13%,transparent)}
.lv-tile-value{display:flex;align-items:baseline;gap:6px;margin-top:10px}
.lv-tile-value b{font-size:32px;line-height:1;font-weight:800;color:var(--on-bg)}
.lv-tile-value span{font-size:12px;color:var(--on-variant)}
.lv-bar{height:7px;margin-top:12px;border-radius:99px;background:color-mix(in srgb,var(--lv-accent,var(--primary)) 14%,transparent);overflow:hidden}
.lv-bar i{display:block;height:100%;border-radius:99px;background:var(--lv-accent,var(--primary));transition:width .5s ease}
.lv-tile-sub{display:flex;justify-content:space-between;gap:8px;margin-top:8px;font-size:11.5px;color:var(--on-variant)}
.lv-pending{color:var(--warn,#a2620c);font-weight:700}
.lv-row{display:flex;align-items:center;gap:12px;padding:12px 20px;border-top:1px solid var(--outline-v);transition:background .12s ease}
.lv-row:first-child{border-top:none}
.lv-row.is-click{cursor:pointer}
.lv-row.is-click:hover{background:color-mix(in srgb,var(--primary) 5%,transparent)}
.lv-row-main{flex:1;min-width:0}
.lv-row-title{font-size:13px;font-weight:600;color:var(--on-bg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lv-row-meta{font-size:12px;color:var(--on-variant);margin-top:2px}
.lv-chevron{color:var(--on-variant);font-size:15px;opacity:.6}
.lv-glyph{flex:none;display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:11px;font-size:17px;color:var(--lv-accent);background:color-mix(in srgb,var(--lv-accent) 14%,transparent)}
.lv-st-pending{--lv-accent:var(--warn,#a2620c)}
.lv-st-approved{--lv-accent:var(--ok,#16a34a)}
.lv-st-rejected{--lv-accent:#dc2626}
.lv-st-cancelled{--lv-accent:#6b7280}
.lv-date{flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;width:46px;height:50px;border-radius:12px;border:1px solid var(--outline-v);background:color-mix(in srgb,var(--primary) 6%,transparent);line-height:1}
.lv-date small{font-size:9.5px;font-weight:800;letter-spacing:.08em;color:var(--primary);text-transform:uppercase}
.lv-date b{font-size:18px;font-weight:800;color:var(--on-bg);margin-top:3px}
.lv-soon{font-size:11px;font-weight:700;color:var(--primary)}
.lv-dot{flex:none;width:10px;height:10px;border-radius:50%;background:var(--lv-accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--lv-accent) 18%,transparent)}
.lv-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media(max-width:700px){.lv-links{grid-template-columns:minmax(0,1fr)}}
.lv-link{display:flex;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--outline-v);border-radius:12px;color:var(--on-bg);text-decoration:none;font-size:12.5px;font-weight:600;transition:border-color .12s ease,background .12s ease}
a.lv-link:hover{border-color:var(--primary);background:color-mix(in srgb,var(--primary) 5%,transparent)}
.lv-link.is-muted{color:var(--on-variant);font-weight:500;background:color-mix(in srgb,var(--on-variant) 5%,transparent)}
.lv-link small{display:block;font-weight:500;color:var(--on-variant);font-size:11.5px;margin-top:2px}
.lv-tiles.is-fit{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.lv-tiles.is-fit .lv-tile{padding:14px 16px}
.lv-panel{background:var(--surface,#fff);border:1px solid var(--outline-v);border-radius:16px;overflow:hidden}
.lv-panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:14px 18px;border-bottom:1px solid var(--outline-v);font-size:13px;font-weight:700;color:var(--on-bg)}
.lv-panel-body{padding:16px 18px}
.lv-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:99px;font-size:11.5px;font-weight:700;color:var(--lv-accent,var(--primary));background:color-mix(in srgb,var(--lv-accent,var(--primary)) 12%,transparent)}
.lv-cal-nav{display:flex;align-items:center;gap:8px}
.lv-cal-btn{display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:32px;padding:0 10px;border:1px solid var(--outline-v);border-radius:9px;background:var(--surface,#fff);color:var(--on-variant);font-size:12px;font-weight:700;cursor:pointer}
.lv-cal-btn:hover{border-color:var(--primary);color:var(--primary)}
.lv-cal-title{min-width:150px;text-align:center;font-size:15px;font-weight:800;color:var(--on-bg)}
.lv-cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}
.lv-cal-dow{padding:9px 0;text-align:center;font-size:10.5px;font-weight:800;letter-spacing:.08em;color:var(--on-variant);background:color-mix(in srgb,var(--on-variant) 6%,transparent);border-bottom:1px solid var(--outline-v)}
.lv-cal-cell{min-height:92px;padding:6px;border-right:1px solid var(--outline-v);border-bottom:1px solid var(--outline-v);text-align:left;background:var(--surface,#fff);font:inherit;color:inherit;cursor:default;display:flex;flex-direction:column;gap:3px;min-width:0}
.lv-cal-cell:nth-child(7n){border-right:none}
.lv-cal-cell.is-empty{background:color-mix(in srgb,var(--on-variant) 5%,transparent)}
.lv-cal-cell.is-weekend{background:color-mix(in srgb,var(--on-variant) 4%,var(--surface,#fff))}
.lv-cal-cell.has-leave{cursor:pointer}
.lv-cal-cell.has-leave:hover{background:color-mix(in srgb,var(--primary) 6%,var(--surface,#fff))}
.lv-cal-cell.is-selected{outline:2px solid var(--primary);outline-offset:-2px;background:color-mix(in srgb,var(--primary) 7%,var(--surface,#fff))}
.lv-cal-cell.is-past .lv-cal-num{opacity:.55}
.lv-cal-num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;font-size:12px;font-weight:600;color:var(--on-variant)}
.lv-cal-cell.is-today .lv-cal-num{background:var(--primary);color:var(--on-primary,#fff);font-weight:800}
.lv-cal-pill{display:block;padding:2px 6px;border-radius:6px;font-size:10.5px;font-weight:600;color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lv-cal-more{font-size:10.5px;font-weight:700;color:var(--primary);padding-left:2px}
@media(max-width:640px){.lv-cal-cell{min-height:56px;padding:3px}.lv-cal-pill{display:none}.lv-cal-cell.has-leave::after{content:"";width:7px;height:7px;border-radius:50%;background:var(--primary);margin:auto 0 2px 4px}}
.lv-legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:11.5px;color:var(--on-variant)}
.lv-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.lv-avatar{flex:none;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;font-size:11.5px;font-weight:800;color:var(--lv-accent,var(--primary));background:color-mix(in srgb,var(--lv-accent,var(--primary)) 15%,transparent)}
.lv-stack{display:flex;height:12px;border-radius:99px;overflow:hidden;background:color-mix(in srgb,var(--on-variant) 12%,transparent)}
.lv-stack i{display:block;height:100%}
.lv-split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.lv-split>.lv-panel:only-child{grid-column:1/-1}
@media(max-width:800px){.lv-split{grid-template-columns:minmax(0,1fr)}}
.lv-meter{margin-bottom:14px}
.lv-meter:last-child{margin-bottom:0}
.lv-meter-head{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;margin-bottom:6px;color:var(--on-variant)}
.lv-meter-head b{color:var(--on-bg)}
.lv-empty{padding:34px 18px;text-align:center;color:var(--on-variant);font-size:13px}
.lv-empty i{display:block;font-size:30px;margin-bottom:8px;opacity:.5}
.lv-strip{display:flex;flex-wrap:wrap;gap:8px}
.lv-strip .lv-chip{padding:6px 12px;font-size:12px}
.lv-actions{display:flex;flex-wrap:wrap;gap:8px}
`;

export function LeaveStyles() {
  return <style>{LEAVE_CSS}</style>;
}
