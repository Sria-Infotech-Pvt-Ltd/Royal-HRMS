// Look of the expense claim form (category tiles, amount box, receipt cards). Scoped under .xf-* so nothing else is touched.
const EXPENSE_FORM_CSS = `
.xf-cats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
@media(max-width:520px){.xf-cats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.xf-cat{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 6px;border:1.5px solid var(--outline-v);border-radius:12px;background:var(--surface,#fff);color:var(--on-variant);font:inherit;font-size:12px;font-weight:700;cursor:pointer;transition:border-color .12s ease,background .12s ease,transform .12s ease}
.xf-cat i{font-size:22px}
.xf-cat:hover{border-color:var(--primary);transform:translateY(-1px)}
.xf-cat.is-on{border-color:var(--primary);color:var(--primary);background:color-mix(in srgb,var(--primary) 9%,transparent);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary) 14%,transparent)}
.xf-cat.is-bad{border-color:var(--error,#dc2626)}
.xf-money{position:relative}
.xf-money b{position:absolute;left:14px;top:50%;transform:translateY(-50%);font-size:17px;font-weight:800;color:var(--on-variant);pointer-events:none}
.xf-money input{padding-left:34px;font-size:18px;font-weight:800}
.xf-words{margin:4px 0 0;font-size:11.5px;color:var(--on-variant)}
.xf-quick{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}
.xf-quick button{padding:3px 10px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);color:var(--on-variant);font:inherit;font-size:11.5px;font-weight:700;cursor:pointer}
.xf-quick button:hover{border-color:var(--primary);color:var(--primary)}
.xf-drop{display:flex;flex-direction:column;align-items:center;gap:4px;padding:20px 14px;border:2px dashed var(--outline-v);border-radius:14px;text-align:center;cursor:pointer;color:var(--on-variant);transition:border-color .12s ease,background .12s ease}
.xf-drop i{font-size:26px;color:var(--primary)}
.xf-drop p{margin:0;font-size:13px;font-weight:700;color:var(--on-bg)}
.xf-drop small{font-size:11.5px}
.xf-drop.is-over,.xf-drop:hover{border-color:var(--primary);background:color-mix(in srgb,var(--primary) 6%,transparent)}
.xf-drop.is-bad{border-color:var(--error,#dc2626)}
.xf-files{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:10px}
@media(max-width:520px){.xf-files{grid-template-columns:minmax(0,1fr)}}
.xf-file{display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid var(--outline-v);border-radius:12px;background:var(--surface,#fff);min-width:0}
.xf-thumb{flex:none;display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:9px;overflow:hidden;font-size:18px;color:#dc2626;background:color-mix(in srgb,#dc2626 12%,transparent)}
.xf-thumb img{width:100%;height:100%;object-fit:cover}
.xf-file-main{flex:1;min-width:0}
.xf-file-name{font-size:12.5px;font-weight:600;color:var(--on-bg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.xf-file-size{font-size:11px;color:var(--on-variant)}
.xf-icon-btn{background:none;border:none;cursor:pointer;color:var(--on-variant);padding:4px;border-radius:6px}
.xf-icon-btn:hover{background:color-mix(in srgb,var(--on-variant) 10%,transparent)}
.xf-summary{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:12px 14px;border-radius:12px;background:color-mix(in srgb,var(--primary) 7%,transparent);border:1px solid color-mix(in srgb,var(--primary) 20%,transparent);font-size:12.5px;color:var(--on-variant)}
.xf-summary b{color:var(--on-bg)}
.xf-summary .xf-total{margin-left:auto;font-size:18px;font-weight:800;color:var(--primary)}
.xf-label-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
`;

export function ExpenseFormStyles() {
  return <style>{EXPENSE_FORM_CSS}</style>;
}
