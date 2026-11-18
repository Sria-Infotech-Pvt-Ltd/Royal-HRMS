// Look of the Separation & Exit list. Scoped under .sp-* so nothing else is touched.
const SEPARATION_CSS = `
.sp-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}
@media(max-width:1000px){.sp-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.sp-tiles{grid-template-columns:minmax(0,1fr)}}
.sp-tile{position:relative;overflow:hidden;display:flex;align-items:center;gap:12px;padding:14px 16px;border:1px solid var(--outline-v);border-radius:16px;background:var(--surface,#fff)}
.sp-tile::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--sp-accent)}
.sp-icon{flex:none;display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:11px;font-size:19px;color:var(--sp-accent);background:color-mix(in srgb,var(--sp-accent) 14%,transparent)}
.sp-tile b{display:block;font-size:26px;line-height:1;font-weight:800;color:var(--on-bg)}
.sp-tile span.sp-tile-label{display:block;margin-top:4px;font-size:11px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--on-variant)}
.sp-bar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}
.sp-seg{display:inline-flex;padding:3px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff)}
.sp-seg button{padding:6px 14px;border:none;border-radius:8px;background:none;font:inherit;font-size:12.5px;font-weight:700;color:var(--on-variant);cursor:pointer}
.sp-seg button.is-on{background:var(--primary);color:var(--on-primary,#fff)}
.sp-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 13px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font:inherit;font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.sp-chip:hover{border-color:var(--primary);color:var(--primary)}
.sp-chip.is-on{border-color:var(--primary);background:color-mix(in srgb,var(--primary) 9%,transparent);color:var(--primary)}
.sp-chip small{padding:0 7px;border-radius:99px;background:color-mix(in srgb,var(--on-variant) 14%,transparent);font-size:11px}
.sp-find{position:relative;min-width:210px}
.sp-find i{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--on-variant)}
.sp-find input{width:100%;padding:8px 12px 8px 33px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff);color:var(--on-bg);font:inherit;font-size:13px}
.sp-person{display:flex;align-items:center;gap:10px}
.sp-avatar{flex:none;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;font-size:11.5px;font-weight:800;color:var(--primary);background:color-mix(in srgb,var(--primary) 13%,transparent)}
.sp-type{display:inline-flex;align-items:center;padding:3px 10px;border-radius:99px;font-size:11.5px;font-weight:700;color:#b45309;background:rgba(217,119,6,.12)}
.sp-left{display:inline-flex;align-items:center;gap:4px;margin-top:3px;padding:2px 8px;border-radius:99px;font-size:10.5px;font-weight:800;color:var(--sp-left);background:color-mix(in srgb,var(--sp-left) 13%,transparent)}
.sp-left.is-soon{--sp-left:#d97706}
.sp-left.is-later{--sp-left:#16a34a}
.sp-left.is-passed{--sp-left:#dc2626}
.sp-table tbody tr{transition:background .12s ease}
.sp-table tbody tr:hover{background:color-mix(in srgb,var(--primary) 4%,transparent)}
.sp-table tr.needs-me>td:first-child{box-shadow:inset 3px 0 0 #dc2626}
.sp-empty{display:flex;flex-direction:column;align-items:center;padding:48px 20px;text-align:center}
.sp-empty-icon{display:inline-flex;align-items:center;justify-content:center;width:64px;height:64px;border-radius:50%;font-size:30px;color:var(--primary);background:color-mix(in srgb,var(--primary) 11%,transparent)}
.sp-empty b{margin-top:12px;font-size:15px;font-weight:800;color:var(--on-bg)}
.sp-empty p{margin:4px 0 0;max-width:420px;font-size:12.5px;color:var(--on-variant)}
`;

export function SeparationStyles() {
  return <style>{SEPARATION_CSS}</style>;
}
