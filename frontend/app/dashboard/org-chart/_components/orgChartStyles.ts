// Styles for the boxes-and-lines org charts (units chart and reporting-line chart). A plain CSS tree: each <li> draws the line to
// its parent, so no chart library is needed.
export const CHART_CSS = `
  .oc-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:6px; padding:0 0 10px; }
  .oc-search { position:relative; flex:1 1 200px; max-width:280px; }
  .oc-search i { position:absolute; left:10px; top:50%; transform:translateY(-50%); font-size:14px; color:var(--outline); }
  .oc-search input { padding-left:32px; }
  .oc-spacer { flex:1; }
  .oc-zoom { font-size:12px; font-weight:600; min-width:40px; text-align:center; color:var(--on-variant); }
  .oc-scroll { overflow:auto; height:calc(100vh - 330px); min-height:520px; border:1px solid var(--outline-v); border-radius:14px; padding:28px 20px 40px; cursor:grab;
    background-color:var(--bg-low); background-image:radial-gradient(var(--outline-v) 1px, transparent 1px); background-size:20px 20px; }
  .oc-empty { padding:40px; text-align:center; color:var(--on-variant); font-size:13px; }
  .oc { min-width:100%; text-align:center; }
  .oc > ul { display:inline-flex; justify-content:center; padding-top:0; }
  .oc ul { display:flex; justify-content:center; padding-top:22px; margin:0; list-style:none; position:relative; }
  .oc li { position:relative; padding:22px 8px 0; display:flex; flex-direction:column; align-items:center; }
  .oc > ul > li { padding-top:0; }
  .oc li::before, .oc li::after { content:""; position:absolute; top:0; width:50%; height:22px; border-top:2px solid var(--outline-v); }
  .oc li::before { right:50%; }
  .oc li::after { left:50%; border-left:2px solid var(--outline-v); }
  .oc li:only-child::before, .oc li:only-child::after { display:none; }
  .oc li:only-child { padding-top:0; }
  .oc li:first-child::before, .oc li:last-child::after { border-top:0; }
  .oc li:last-child::before { border-right:2px solid var(--outline-v); border-radius:0 8px 0 0; }
  .oc li:first-child::after { border-radius:8px 0 0 0; }
  .oc > ul > li::before, .oc > ul > li::after { display:none; }
  .oc ul ul::before { content:""; position:absolute; top:0; left:50%; height:22px; border-left:2px solid var(--outline-v); }
  .oc-box-wrap { position:relative; padding-bottom:12px; }
  .oc-box { width:224px; text-align:left; background:linear-gradient(180deg, var(--surface, #fff), var(--bg-low)); border:1px solid var(--outline-v); border-top:4px solid var(--outline); border-radius:14px; padding:12px 14px; cursor:pointer;
    box-shadow:0 1px 2px rgba(15,23,42,.06), 0 6px 16px rgba(15,23,42,.06); transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
  .oc-box:hover { border-color:var(--primary); transform:translateY(-2px); box-shadow:0 2px 4px rgba(15,23,42,.08), 0 14px 28px rgba(15,23,42,.14); }
  .oc-ok { border-top-color:var(--success); }
  .oc-mid { border-top-color:var(--warn); }
  .oc-low { border-top-color:var(--error); }
  .oc-vacant { border-top-color:var(--warn); }
  .oc-filled { border-top-color:var(--primary); }
  .oc-box:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
  .oc-box-sel { border-color:var(--primary); box-shadow:0 0 0 3px rgba(124,58,237,.18); }
  .oc-box-hit { border-color:#eab308; box-shadow:0 0 0 3px rgba(234,179,8,.3); }
  .oc-dim { opacity:.38; }
  .oc-name { font-size:13px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .oc-sub { font-size:11px; color:var(--outline); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .oc-head { font-size:11.5px; color:var(--on-variant); margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; gap:5px; }
  .oc-head .ti-crown { color:var(--warn); }
  .oc-warn { color:var(--warn); font-weight:600; }
  .oc-muted { color:var(--outline); }
  .oc-bar { height:5px; border-radius:3px; background:var(--outline-v); margin-top:8px; overflow:hidden; }
  .oc-bar span { display:block; height:100%; background:var(--success); }
  .oc-foot { display:flex; align-items:center; justify-content:space-between; gap:6px; margin-top:7px; font-size:11px; color:var(--on-variant); }
  .oc-avatars { display:flex; }
  .oc-avatar { width:20px; height:20px; border-radius:50%; background:var(--success-c); color:var(--success); font-size:8.5px; font-weight:750; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; border:1.5px solid var(--surface, #fff); }
  .oc-avatars .oc-avatar { margin-left:-5px; }
  .oc-avatar-vacant { background:var(--warn-c, rgba(245,158,11,.14)); color:var(--warn); }
  .oc-more { background:var(--bg-low); color:var(--on-variant); }
  .oc-seats { margin-top:8px; border-top:1px solid var(--outline-v); padding-top:6px; display:grid; gap:4px; }
  .oc-seat { display:flex; align-items:center; gap:6px; font-size:11px; min-width:0; }
  .oc-seat-title { flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .oc-seat .ti-crown { color:var(--warn); font-size:11px; }
  .oc-toggle { position:absolute; left:50%; bottom:0; transform:translateX(-50%); min-width:22px; height:22px; border-radius:11px; border:1px solid var(--outline-v); background:var(--surface, #fff); color:var(--on-variant); font-size:11px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; padding:0 6px; z-index:1; }
  .oc-toggle:hover { border-color:var(--primary); color:var(--primary); }
  @media (max-width: 700px) {
    .oc-scroll { height:calc(100vh - 280px); min-height:420px; padding:18px 10px 28px; }
    .oc-search { max-width:none; flex-basis:100%; }
  }
  @media print {
    body * { visibility:hidden; }
    .oc-scroll, .oc-scroll * { visibility:visible; }
    .oc-scroll { position:absolute; left:0; top:0; width:100%; height:auto; min-height:0; overflow:visible; border:0; background:#fff; }
    .oc-toggle { display:none; }
  }
`;
