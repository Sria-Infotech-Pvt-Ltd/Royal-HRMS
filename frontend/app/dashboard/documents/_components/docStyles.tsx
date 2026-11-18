// Extra look for the Document Center (clickable stat tiles, view switch, list rows, "new" chip). Scoped under .dx-*.
const DOC_CSS = `
.dx-stat{position:relative;overflow:hidden;text-align:left;font:inherit;cursor:pointer;transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
.dx-stat::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--dx-accent)}
.dx-stat:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(76,29,149,.10)}
.dx-stat.is-on{border-color:var(--dx-accent)!important;box-shadow:0 0 0 3px color-mix(in srgb,var(--dx-accent) 16%,transparent)}
.dx-tools{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-left:auto}
.dx-select{padding:7px 10px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff);color:var(--on-bg);font:inherit;font-size:12.5px}
.dx-views{display:inline-flex;padding:3px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff)}
.dx-views button{display:inline-flex;align-items:center;justify-content:center;width:34px;height:30px;border:none;border-radius:8px;background:none;font-size:16px;color:var(--on-variant);cursor:pointer}
.dx-views button.is-on{background:var(--primary);color:var(--on-primary,#fff)}
.dx-new{display:inline-block;padding:1px 8px;border-radius:99px;font-size:10px;font-weight:800;letter-spacing:.04em;color:#fff;background:#16a34a}
.dx-tile-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.dx-quick{display:flex;gap:4px;opacity:0;transition:opacity .12s ease}
.doc-tile:hover .dx-quick,.dx-row:hover .dx-quick,.dx-quick:focus-within{opacity:1}
@media(hover:none){.dx-quick{opacity:1}}
.dx-quick button,.dx-quick a{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:1px solid var(--outline-v);border-radius:8px;background:var(--surface,#fff);color:var(--on-variant);font-size:14px;cursor:pointer;text-decoration:none}
.dx-quick button:hover,.dx-quick a:hover{border-color:var(--primary);color:var(--primary)}
.dx-list{border:1px solid var(--outline-v);border-radius:16px;background:var(--surface,#fff);overflow:hidden}
.dx-row{display:flex;align-items:center;gap:14px;padding:11px 16px;border-top:1px solid var(--outline-v);cursor:pointer;transition:background .12s ease}
.dx-row:first-child{border-top:none}
.dx-row:hover{background:color-mix(in srgb,var(--primary) 4%,transparent)}
.dx-row .doc-icon{flex:none;width:38px;height:38px;font-size:18px}
.dx-row-main{flex:1;min-width:0}
.dx-row-title{display:flex;align-items:center;gap:8px;font-size:13.5px;font-weight:700;color:var(--on-bg)}
.dx-row-title span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dx-row-meta{margin-top:2px;font-size:11.5px;color:var(--on-variant)}
.dx-row-col{flex:none;width:120px;font-size:12px;color:var(--on-variant)}
@media(max-width:760px){.dx-row-col{display:none}.dx-row{padding:10px 12px}}
@media(max-width:480px){.dc-stats-row.dc-stats-row{grid-template-columns:minmax(0,1fr)}}
.dx-empty{display:flex;flex-direction:column;align-items:center;padding:52px 16px;text-align:center}
.dx-empty-icon{display:inline-flex;align-items:center;justify-content:center;width:68px;height:68px;border-radius:50%;font-size:32px;color:var(--primary);background:color-mix(in srgb,var(--primary) 11%,transparent)}
.dx-empty b{margin-top:12px;font-size:15px;font-weight:800;color:var(--on-bg)}
.dx-empty p{margin:4px 0 0;max-width:380px;font-size:12.5px;color:var(--on-variant)}
`;

export function DocStyles() {
  return <style>{DOC_CSS}</style>;
}
