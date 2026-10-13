"use client";
/* eslint-disable @next/next/no-img-element */
// Plain <img>: logo/photo/signature are remote (Cloudinary, signed) URLs sized in mm for print.

// Front/back ID card template reproducing the approved reference design
// (navy + gold, circular photo, icon rows, website footer bar). Every size
// is in mm so the printed card comes out at exactly 50 × 85 mm; on screen
// the preview is enlarged with CSS zoom (see .idc-preview).

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { frontRows, idCardPrintCss, type IdCardData, type PrintLayout } from "@/lib/idCard";

const NAVY = "#111c3d";
const GOLD = "#b8862b";

export const ID_CARD_CSS = `
.idc-card {
  width: 50mm; height: 85mm; background: #fff; color: ${NAVY};
  position: relative; overflow: hidden; display: flex; flex-direction: column;
  font-family: "Noto Sans", "Open Sans", "Segoe UI", Arial, sans-serif;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.idc-card * { box-sizing: border-box; }
.idc-logo { height: 8.6mm; margin: 2mm auto 0; max-width: 34mm; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.idc-logo img { max-height: 100%; max-width: 100%; object-fit: contain; display: block; }
.idc-logo-text { font-weight: 700; font-size: 2.3mm; text-align: center; letter-spacing: .03em; }
.idc-photo { width: 17.6mm; height: 17.6mm; margin: 1.8mm auto 0; border-radius: 50%; border: .3mm solid ${GOLD}; padding: .45mm; background: #fff; flex-shrink: 0; }
.idc-photo img, .idc-photo-empty { width: 100%; height: 100%; border-radius: 50%; display: block; object-fit: cover; }
.idc-photo-empty { background: #eef1f7; color: #9aa3b8; display: flex; align-items: center; justify-content: center; font-size: 8mm; }
.idc-name { margin-top: 2mm; padding: 0 3mm; text-align: center; font-weight: 700; font-size: 2.15mm; line-height: 1.2; letter-spacing: .02em; text-transform: uppercase; }
.idc-desig { padding: 0 3mm; text-align: center; font-size: 1.85mm; line-height: 1.2; letter-spacing: .02em; text-transform: uppercase; }
.idc-name, .idc-desig { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.idc-rule { height: .22mm; width: 17mm; margin: .9mm auto; background: linear-gradient(90deg, transparent, ${GOLD} 20%, ${GOLD} 80%, transparent); flex-shrink: 0; }
.idc-rows { margin-top: 2.2mm; padding: 0 3mm 0 4.2mm; display: flex; flex-direction: column; }
.idc-row { position: relative; display: flex; align-items: center; gap: 1.5mm; height: 5.9mm; }
.idc-row:not(:last-child)::after { content: ""; position: absolute; left: 8mm; right: 1.5mm; bottom: 0; height: .22mm; background: linear-gradient(90deg, transparent, ${GOLD} 12%, ${GOLD} 88%, transparent); }
.idc-ico { width: 4.8mm; height: 4.8mm; border-radius: 50%; background: ${NAVY}; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 2.8mm; flex-shrink: 0; }
.idc-row-text { font-size: 1.85mm; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.idc-footer { margin-top: auto; height: 4.9mm; flex-shrink: 0; background: ${NAVY}; color: #fff; display: flex; align-items: center; justify-content: center; gap: 1.2mm; font-size: 1.7mm; padding: 0 2mm; white-space: nowrap; overflow: hidden; }
.idc-footer i { font-size: 2.4mm; }
.idc-back-body { padding: 2mm 3mm 0 4.4mm; display: flex; flex-direction: column; flex: 1; min-height: 0; }
.idc-sec { display: flex; gap: 1.3mm; }
.idc-sec .idc-ico { width: 3mm; height: 3mm; font-size: 1.8mm; margin-top: .1mm; }
.idc-sec-title { font-weight: 700; font-size: 1.8mm; line-height: 1.3; }
.idc-sec-text { font-size: 1.7mm; line-height: 1.3; margin-top: .3mm; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.idc-sec-text.one { -webkit-line-clamp: 1; }
.idc-sec-rule { height: .2mm; width: 17mm; margin: 1.5mm auto; background: linear-gradient(90deg, transparent, ${GOLD} 20%, ${GOLD} 80%, transparent); flex-shrink: 0; }
.idc-terms-pill { align-self: center; margin-top: .6mm; background: ${NAVY}; color: #c8963a; font-weight: 700; font-size: 1.85mm; padding: .55mm 2.4mm; border-radius: 2mm; }
.idc-terms { margin: 1.3mm 0 0; padding-left: 3.2mm; font-size: 1.8mm; line-height: 1.3; }
.idc-terms li { margin-bottom: .3mm; }
.idc-sign { margin-top: auto; align-self: flex-end; text-align: center; padding-bottom: .8mm; }
.idc-sign-img { height: 7mm; display: flex; align-items: flex-end; justify-content: center; }
.idc-sign-img img { max-height: 7mm; max-width: 15mm; object-fit: contain; }
.idc-sign-label { font-weight: 700; font-size: 1.55mm; }
.idc-preview { zoom: 1.7; }
`;

function Logo({ data }: { data: IdCardData }) {
  return (
    <div className="idc-logo">
      {data.company.logo_url
        ? <img src={data.company.logo_url} alt="" />
        : <div className="idc-logo-text">{data.company.name ?? ""}</div>}
    </div>
  );
}

function Footer({ data }: { data: IdCardData }) {
  return (
    <div className="idc-footer">
      {data.company.website && <><i className="ti ti-world" />{data.company.website}</>}
    </div>
  );
}

export function IdCardFront({ data }: { data: IdCardData }) {
  const emp = data.employee;
  return (
    <div className="idc-card">
      <Logo data={data} />
      <div className="idc-photo">
        {emp.photo_url
          ? <img src={emp.photo_url} alt="" />
          : <div className="idc-photo-empty"><i className="ti ti-user" /></div>}
      </div>
      <div className="idc-name">{emp.full_name}</div>
      {emp.designation && <><div className="idc-rule" /><div className="idc-desig">{emp.designation}</div></>}
      <div className="idc-rows">
        {frontRows(emp).map(r => (
          <div key={r.key} className="idc-row">
            <span className="idc-ico"><i className={`ti ${r.icon}`} /></span>
            <span className="idc-row-text">{r.label}: {r.value}</span>
          </div>
        ))}
      </div>
      <Footer data={data} />
    </div>
  );
}

export function IdCardBack({ data }: { data: IdCardData }) {
  const emp = data.employee;
  const contact = [emp.phone, emp.email].filter(Boolean) as string[];
  const sections = [
    emp.residential_address && { key: "res", icon: "ti-map-pin", title: "Residential Address", lines: [emp.residential_address] },
    data.company.office_address && { key: "off", icon: "ti-building", title: "Office Address", lines: [data.company.office_address] },
    contact.length > 0 && { key: "con", icon: "ti-address-book", title: "Contact Details", lines: contact, single: true },
  ].filter(Boolean) as { key: string; icon: string; title: string; lines: string[]; single?: boolean }[];

  return (
    <div className="idc-card">
      <Logo data={data} />
      <div className="idc-back-body">
        {sections.map((s, i) => (
          <div key={s.key}>
            {i > 0 && <div className="idc-sec-rule" />}
            <div className="idc-sec">
              <span className="idc-ico"><i className={`ti ${s.icon}`} /></span>
              <div style={{ minWidth: 0 }}>
                <div className="idc-sec-title">{s.title}</div>
                {s.lines.map((line, j) => (
                  <div key={j} className={`idc-sec-text${s.single ? " one" : ""}`}>{line}</div>
                ))}
              </div>
            </div>
          </div>
        ))}
        {sections.length > 0 && <div className="idc-sec-rule" />}
        {data.card.terms.length > 0 && (
          <>
            <div className="idc-terms-pill">Terms &amp; Conditions:</div>
            <ul className="idc-terms">
              {data.card.terms.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          </>
        )}
        <div className="idc-sign">
          <div className="idc-sign-img">
            {data.card.signature_url && <img src={data.card.signature_url} alt="" />}
          </div>
          <div className="idc-sign-label">{data.card.signatory_label}</div>
        </div>
      </div>
      <Footer data={data} />
    </div>
  );
}

/** Screen preview: both faces side by side, enlarged. */
export function IdCardPreview({ data }: { data: IdCardData }) {
  return (
    <div style={{ display: "flex", gap: 28, flexWrap: "wrap", justifyContent: "center" }}>
      {(["Front", "Back"] as const).map(side => (
        <div key={side} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em" }}>
            {side}
          </div>
          <div className="idc-preview" style={{ boxShadow: "0 2px 12px rgba(17,28,61,.18)", borderRadius: 1, border: "1px solid #e3e7ef" }}>
            {side === "Front" ? <IdCardFront data={data} /> : <IdCardBack data={data} />}
          </div>
        </div>
      ))}
      <style>{ID_CARD_CSS}</style>
    </div>
  );
}

/** Print-only copy of both faces, portalled directly under <body> so the
 *  print stylesheet can hide every other part of the app. */
export function IdCardPrintSheet({ data, layout }: { data: IdCardData; layout: PrintLayout }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(
    <div className="idc-print-root" data-layout={layout}>
      <style>{ID_CARD_CSS + idCardPrintCss(layout)}</style>
      <div className="idc-print-face"><IdCardFront data={data} /></div>
      <div className="idc-print-face"><IdCardBack data={data} /></div>
    </div>,
    document.body,
  );
}
