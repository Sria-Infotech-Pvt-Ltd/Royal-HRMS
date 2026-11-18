// Look of the Attendance Approval tab (cycle cards, sign-off steps, totals, search bar). Scoped under .aa-* so nothing else is touched.
const ATTENDANCE_APPROVAL_CSS = `
.aa-cycles{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.aa-cycle{display:flex;flex-direction:column;gap:6px;padding:14px 16px;border:1.5px solid var(--outline-v);border-radius:14px;background:var(--surface,#fff);text-align:left;font:inherit;color:var(--on-bg);cursor:pointer;transition:border-color .12s ease,box-shadow .12s ease,transform .12s ease}
.aa-cycle:hover{transform:translateY(-1px);border-color:var(--primary)}
.aa-cycle.is-on{border-color:var(--primary);background:color-mix(in srgb,var(--primary) 7%,transparent);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary) 14%,transparent)}
.aa-cycle b{font-size:14px;font-weight:800}
.aa-cycle small{font-size:11.5px;color:var(--on-variant)}
.aa-cycle-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:2px}
.aa-chip{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:99px;font-size:10.5px;font-weight:800;color:var(--aa-chip,var(--on-variant));background:color-mix(in srgb,var(--aa-chip,var(--on-variant)) 12%,transparent)}
.aa-chip.is-done{--aa-chip:#16a34a}
.aa-chip.is-open{--aa-chip:#d97706}
.aa-steps-wrap{padding:16px 20px;border-bottom:1px solid var(--outline-v);display:flex;flex-direction:column;gap:12px}
.aa-steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0}
@media(max-width:760px){.aa-steps{grid-template-columns:minmax(0,1fr);gap:10px}}
.aa-step{position:relative;display:flex;align-items:center;gap:10px;padding-right:12px}
.aa-step:not(:last-child)::after{content:"";position:absolute;left:44px;right:8px;top:18px;height:2px;background:var(--outline-v)}
@media(max-width:760px){.aa-step:not(:last-child)::after{display:none}}
.aa-step.is-done:not(:last-child)::after{background:#16a34a}
.aa-step>div{position:relative;z-index:1;background:var(--surface,#fff);padding:0 8px 0 0;min-width:0}
.aa-step-dot{position:relative;z-index:1;flex:none;display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;font-size:17px;color:var(--on-variant);background:var(--surface,#fff);border:2px solid var(--outline-v)}
.aa-step.is-done .aa-step-dot{color:#fff;background:#16a34a;border-color:#16a34a}
.aa-step.is-current .aa-step-dot{color:var(--primary);border-color:var(--primary);box-shadow:0 0 0 4px color-mix(in srgb,var(--primary) 16%,transparent)}
.aa-step-title{font-size:13px;font-weight:800;color:var(--on-bg)}
.aa-step-detail{font-size:11.5px;color:var(--on-variant)}
.aa-tag{align-self:flex-start;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:800;color:#b45309;background:rgba(217,119,6,.12)}
.aa-managers{display:flex;flex-wrap:wrap;gap:8px}
.aa-manager{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border:1.5px solid var(--outline-v);border-radius:99px;font-size:12px;background:var(--bg-low,transparent)}
.aa-manager.is-done{border-color:#16a34a;background:rgba(34,197,94,.07)}
.aa-manager i{color:var(--on-variant)}
.aa-manager.is-done i{color:#16a34a}
.aa-manager small{font-size:11px;color:var(--on-variant)}
.aa-manager em{font-style:normal;padding:1px 7px;border-radius:99px;font-size:10px;font-weight:800;color:#b45309;background:rgba(217,119,6,.12)}
.aa-totals{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;padding:14px 20px;border-bottom:1px solid var(--outline-v)}
.aa-total{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px;background:color-mix(in srgb,var(--aa-accent) 8%,transparent)}
.aa-total.is-alert{background:color-mix(in srgb,var(--aa-accent) 15%,transparent);box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--aa-accent) 45%,transparent)}
.aa-total-icon{flex:none;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:9px;font-size:16px;color:var(--aa-accent);background:color-mix(in srgb,var(--aa-accent) 16%,transparent)}
.aa-total b{display:block;font-size:20px;line-height:1.1;font-weight:800;color:var(--on-bg)}
.aa-total span{font-size:11px;font-weight:700;color:var(--on-variant)}
.aa-find{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:12px 20px;border-bottom:1px solid var(--outline-v)}
.aa-find-box{position:relative;flex:1;min-width:200px;max-width:360px}
.aa-find-box i{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--on-variant)}
.aa-find-box input{width:100%;padding:8px 12px 8px 33px;border:1px solid var(--outline-v);border-radius:10px;background:var(--surface,#fff);color:var(--on-bg);font:inherit;font-size:13px}
.aa-filter{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1px solid var(--outline-v);border-radius:99px;background:var(--surface,#fff);font:inherit;font-size:12px;font-weight:700;color:var(--on-variant);cursor:pointer}
.aa-filter:hover,.aa-filter.is-on{border-color:var(--primary);color:var(--primary)}
.aa-filter.is-on{background:color-mix(in srgb,var(--primary) 9%,transparent)}
.aa-find-count{margin-left:auto;font-size:12px;color:var(--on-variant)}
.aa-avatar{flex:none;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;font-size:11px;font-weight:800;color:var(--primary);background:color-mix(in srgb,var(--primary) 13%,transparent)}
.aa-bar{display:flex;height:5px;margin-top:5px;border-radius:99px;overflow:hidden;background:color-mix(in srgb,var(--on-variant) 14%,transparent)}
.aa-bar i{display:block;height:100%}
.aa-empty{padding:44px 20px;text-align:center;color:var(--on-variant);font-size:13px}
.aa-empty i{display:block;margin-bottom:10px;font-size:34px;color:#16a34a}
`;

export function AttendanceApprovalStyles() {
  return <style>{ATTENDANCE_APPROVAL_CSS}</style>;
}
